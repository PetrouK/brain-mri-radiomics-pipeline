from pathlib import Path
from radiomics import featureextractor
import SimpleITK as sitk
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

from mri_pipeline.utils.files import ensure_dir, get_patient_dirs, list_nifti_files

IGNORED_ROI_LABEL_FOLDERS = {"radiomics"}


def make_binary_mask(mask):
    binary_mask = sitk.Cast(mask > 0, sitk.sitkUInt8)
    return binary_mask


def collect_radiomics_jobs(
    image_root,
    roi_root,
):
    image_root = Path(image_root)
    roi_root = Path(roi_root)
    jobs = []

    cases = get_patient_dirs(image_root)
    roi_label_folders = [
        folder for folder in get_patient_dirs(roi_root)
        if folder.name.lower() not in IGNORED_ROI_LABEL_FOLDERS
    ]

    for case in cases:
        case_id = case.name
        image_paths = list_nifti_files(case)
        if not image_paths:
            print(f"[Warning] No image found for {case_id}. Skipping.")
            continue

        if len(image_paths) > 1:
            print(f"[Warning] Multiple images found for {case_id}. Using: {image_paths[0].name}")

        image_path = image_paths[0]
        
        for roi_label in roi_label_folders:
            roi_id = roi_label.name
            tmp_path = roi_label / case_id
            if not tmp_path.exists():
                print(f"[Warning] No ROI folder found for {roi_id}/{case_id}. Skipping.")
                continue
            roi_paths = list_nifti_files(tmp_path)
            if not roi_paths:
                print(f"[Warning] No ROI masks found for {roi_id}/{case_id}. Skipping.")
                continue
            for roi_path in roi_paths:
                job = {
                    "case_id": case_id,
                    "roi_label": roi_id,
                    "image_path": image_path,
                    "mask_path": roi_path
                }
                jobs.append(job)

    return jobs

def group_jobs_by_case(jobs):
    grouped_jobs = {}

    for job in jobs:
        case_id = job["case_id"]
        if case_id not in grouped_jobs:
            grouped_jobs[case_id] = []
            
        grouped_jobs[case_id].append(job)

    return grouped_jobs

def create_radiomics_extractor(discretization_mode, discretization_value):
    extractor = featureextractor.RadiomicsFeatureExtractor()

    extractor.disableAllFeatures()

    for feature_class in ["shape","firstorder", "glcm", "glrlm", "glszm", "gldm", "ngtdm"]:
        extractor.enableFeatureClassByName(feature_class)

    extractor.enableImageTypeByName("Original")

    settings = {
        "resampledPixelSpacing": None,
        "normalize": False,
        "interpolator": None,
    }

    if discretization_mode == "binWidth":
        settings["binWidth"] = discretization_value
    elif discretization_mode == "binCount":
        settings["binCount"] = discretization_value
    else:
        raise ValueError(f"Unknown discretization mode: {discretization_mode}")

    extractor.settings.update(settings)
    return extractor

def compute_roi_intensity_range(image, mask):
    mask = make_binary_mask(mask)

    stats = sitk.LabelStatisticsImageFilter()
    stats.Execute(image, mask)

    if not stats.HasLabel(1):
        return None

    min_value = stats.GetMinimum(1)
    max_value = stats.GetMaximum(1)

    return max_value - min_value

def resolve_discretization_value(
    jobs,
    discretization_mode,
    input_value,
    values_are_target_bins=False,
):
    if discretization_mode == "binCount":
        if int(input_value) != input_value:
            raise ValueError(f"binCount must be an integer value. Got: {input_value}")
        return int(input_value)

    if discretization_mode != "binWidth":
        raise ValueError(f"Unknown discretization mode: {discretization_mode}")

    if not values_are_target_bins:
        return input_value

    roi_ranges = []

    for job in jobs:
        image = sitk.ReadImage(str(job["image_path"]), sitk.sitkFloat64)
        mask = make_binary_mask(sitk.ReadImage(str(job["mask_path"]), sitk.sitkUInt8))

        roi_range = compute_roi_intensity_range(image, mask)

        if roi_range is not None:
            roi_ranges.append(roi_range)

    if not roi_ranges:
        raise ValueError("Cannot compute binWidth because no valid ROI ranges were found.")

    average_roi_range = sum(roi_ranges) / len(roi_ranges)

    return average_roi_range / input_value


def format_discretization_value(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).replace(".", "p")



def process_radiomics_case(case_jobs, discretization_mode, discretization_value):
    rows = []

    if not case_jobs:
        return rows

    image_path = case_jobs[0]["image_path"]

    image = sitk.ReadImage(str(image_path), sitk.sitkFloat64)

    extractor = create_radiomics_extractor(discretization_mode, discretization_value)

    
    for row in case_jobs:
        mask_path = row["mask_path"]
        mask = sitk.ReadImage(str(mask_path), sitk.sitkUInt8)
        mask = make_binary_mask(mask)
        roi_range = compute_roi_intensity_range(image, mask)
        
        features = extractor.execute(image, mask, label=1)
    
        result = {
            "Case_ID": row["case_id"],
            "ROI_Label": row["roi_label"],
            "Image": image_path.name,
            "Mask": mask_path.name,
            "DiscretizationMode": discretization_mode,
            "DiscretizationValue": discretization_value,
            "ROI_Range": roi_range,
        }
    
        if discretization_mode == "binWidth" and roi_range is not None:
            result["Actual_Bins"] = roi_range / discretization_value
        else:
            result["Actual_Bins"] = None
    
        for feature_name, feature_value in features.items():
            if feature_name.startswith("diagnostics_"):
                continue
    
            result[feature_name] = feature_value

        rows.append(result)

    return rows


def extract_radiomics_features(
        image_root,
        roi_root,
        output_root,
        discretization_mode,
        discretization_values,
        values_are_target_bins=False,
        max_workers=1,
    ):

    jobs = collect_radiomics_jobs(image_root, roi_root)

    if not jobs:
        raise ValueError("No radiomics jobs found. Check image_root and roi_root structure.")


    grouped_jobs = group_jobs_by_case(jobs)
    output_root = ensure_dir(output_root)
    output_files = []

    for input_value in discretization_values:
        resolved_value = resolve_discretization_value(jobs, discretization_mode, input_value, values_are_target_bins)

        rows = []
        if max_workers == 1:
            for case_jobs in grouped_jobs.values():
                case_rows = process_radiomics_case(
                    case_jobs=case_jobs,
                    discretization_mode=discretization_mode,
                    discretization_value=resolved_value,
                )

                for row in case_rows:
                    row["InputValue"] = input_value
                    row["ValuesAreTargetBins"] = values_are_target_bins
                    rows.append(row)
        else:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = []

                for case_jobs in grouped_jobs.values():
                    future = executor.submit(
                        process_radiomics_case,
                        case_jobs,
                        discretization_mode,
                        resolved_value,
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    case_rows = future.result()

                    for row in case_rows:
                        row["InputValue"] = input_value
                        row["ValuesAreTargetBins"] = values_are_target_bins
                        rows.append(row)

        df = pd.DataFrame(rows)

        value_name = format_discretization_value(input_value)
        if discretization_mode == "binWidth" and values_are_target_bins:
            output_file = output_root / f"Features_binWidth_targetBins_{value_name}.xlsx"
        else:
            output_file = output_root / f"Features_{discretization_mode}_{value_name}.xlsx"

        df.to_excel(output_file, index=False)
        output_files.append(output_file)

    return output_files





