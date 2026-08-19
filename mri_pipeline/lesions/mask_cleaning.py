from pathlib import Path
import SimpleITK as sitk

from mri_pipeline.utils.files import ensure_dir, build_output_path, get_patient_dirs


def images_have_same_geometry(image_a, image_b):
    return (
        image_a.GetSize() == image_b.GetSize()
        and image_a.GetSpacing() == image_b.GetSpacing()
        and image_a.GetOrigin() == image_b.GetOrigin()
        and image_a.GetDirection() == image_b.GetDirection()
    )

def read_binary_mask(mask_path):
    mask_path = Path(mask_path)

    mask_image = sitk.ReadImage(str(mask_path))

    binary_mask = mask_image > 0
    binary_mask = sitk.Cast(binary_mask, sitk.sitkUInt8)

    return binary_mask

def check_same_geometry(reference_mask, other_mask, other_name):

    if not images_have_same_geometry(reference_mask, other_mask):
        raise ValueError(
            f"ROI mask and {other_name} do not have the same geometry. "
            "Resample masks to the same reference image before cleaning."
        )

    return True

def dilate_mask(mask_image, radius=1):

    if radius <= 0:
        return mask_image

    dilated = sitk.BinaryDilate(
        mask_image,
        kernelRadius=[radius, radius, radius],
        kernelType=sitk.sitkBall,
        foregroundValue=1
    )

    return dilated

def clean_roi_mask(
        roi_mask_path,
        output_path,
        allowed_mask_paths=None,
        forbidden_mask_paths=None,
        exclusion_mask_path=None,
        exclusion_dilation=1,
    ):

    output_path = Path(output_path)

    roi = read_binary_mask(roi_mask_path)
    cleaned = roi
    allowed_mask_paths = allowed_mask_paths or []
    forbidden_mask_paths = forbidden_mask_paths or []

    for allowed_mask_path in allowed_mask_paths:
        allowed = read_binary_mask(allowed_mask_path)
        check_same_geometry(roi, allowed, "allowed mask")
        cleaned = cleaned & allowed

    for forbidden_mask_path in forbidden_mask_paths:
        forbidden = read_binary_mask(forbidden_mask_path)
        check_same_geometry(roi, forbidden, "forbidden mask")
        cleaned = cleaned & (forbidden == 0)

    if exclusion_mask_path is not None:
        exclusion = read_binary_mask(exclusion_mask_path)
        check_same_geometry(roi, exclusion, "exclusion mask")
        exclusion = dilate_mask(exclusion, exclusion_dilation)
        cleaned = cleaned & (exclusion == 0)

    ensure_dir(output_path.parent)
    sitk.WriteImage(cleaned, str(output_path))
    return output_path

def build_cleaned_mask_path(output_root, roi_mask_path, suffix="_cleaned"):

    output_root = Path(output_root)
    roi_mask_path = Path(roi_mask_path)

    output_path = build_output_path(
        input_path=roi_mask_path,
        suffix=suffix,
        output_dir=output_root
    )

    return output_path

def clean_roi_mask_file(
        roi_mask_path,
        output_root,
        allowed_mask_paths=None,
        forbidden_mask_paths=None,
        exclusion_mask_path=None,
        exclusion_dilation=1,
        suffix="_cleaned",
        overwrite_existing=False,
    ):

    roi_mask_path = Path(roi_mask_path)
    allowed_mask_paths = [Path(path) for path in allowed_mask_paths] if allowed_mask_paths is not None else []
    forbidden_mask_paths = [Path(path) for path in forbidden_mask_paths] if forbidden_mask_paths is not None else []
    exclusion_mask_path = Path(exclusion_mask_path) if exclusion_mask_path is not None else None

    output_path = build_cleaned_mask_path(output_root, roi_mask_path, suffix)
    if output_path.exists() and not overwrite_existing:
        print(f"[Skip] Cleaned ROI mask already exists: {output_path}")
        return output_path


    output_path = clean_roi_mask(
        roi_mask_path=roi_mask_path,
        allowed_mask_paths=allowed_mask_paths,
        forbidden_mask_paths=forbidden_mask_paths,
        output_path=output_path,
        exclusion_mask_path=exclusion_mask_path,
        exclusion_dilation=exclusion_dilation,
    )
    return output_path

def find_matching_mask(mask_root, case_id, pattern="*.nii*", timepoint=None):
    matches = find_matching_masks(
        mask_root=mask_root,
        case_id=case_id,
        pattern=pattern,
        timepoint=timepoint,
    )

    return matches[0] if matches else None

def find_matching_masks(mask_root, case_id, pattern="*.nii*", timepoint=None):
    mask_root = Path(mask_root)
    case_folder = mask_root / str(case_id)

    if not case_folder.exists() or not case_folder.is_dir():
        return []

    search_folder = case_folder

    if timepoint is not None:
        search_folder = case_folder / str(timepoint)

        if not search_folder.exists() or not search_folder.is_dir():
            return []

    matches = sorted(
        path for path in search_folder.glob(pattern)
        if path.is_file()
    )

    return matches

def clean_roi_masks_folder(
        roi_root,
        output_root,
        allowed_roots=None,
        forbidden_roots=None,
        exclusion_root=None,
        exclusion_dilation=1,
        suffix="_cleaned",
        roi_timepoint=None,
        allowed_timepoint=None,
        forbidden_timepoint=None,
        exclusion_timepoint=None,
        overwrite_existing=False,
    ):

    roi_root = Path(roi_root)
    output_root = Path(output_root)
    allowed_roots = [Path(root) for root in allowed_roots] if allowed_roots is not None else []
    forbidden_roots = [Path(root) for root in forbidden_roots] if forbidden_roots is not None else []
    exclusion_root = Path(exclusion_root) if exclusion_root is not None else None

    if not allowed_roots and not forbidden_roots and exclusion_root is None:
        raise ValueError(
            "At least one of allowed_root, forbidden_root, or exclusion_root is required for ROI cleaning."
        )

    patients = get_patient_dirs(roi_root)
    created_files = []

    for patient in patients:

        case_id = patient.name
        roi_image_paths = find_matching_masks(roi_root, case_id, timepoint=roi_timepoint)

        if not roi_image_paths:
            print(f"[Warning] No ROI mask found for {case_id}. Skipping.")
            continue

        allowed_mask_paths = []
        for allowed_root in allowed_roots:
            allowed_mask_path = find_matching_mask(allowed_root, case_id, timepoint=allowed_timepoint)
            if allowed_mask_path is None:
                print(f"[Warning] No allowed mask found for {case_id} in {allowed_root}. Skipping.")
                allowed_mask_paths = None
                break
            allowed_mask_paths.append(allowed_mask_path)

        if allowed_mask_paths is None:
            continue

        forbidden_mask_paths = []
        for forbidden_root in forbidden_roots:
            forbidden_mask_path = find_matching_mask(forbidden_root, case_id, timepoint=forbidden_timepoint)
            if forbidden_mask_path is None:
                print(f"[Warning] No forbidden mask found for {case_id} in {forbidden_root}. Skipping.")
                forbidden_mask_paths = None
                break
            forbidden_mask_paths.append(forbidden_mask_path)

        if forbidden_mask_paths is None:
            continue

        if exclusion_root is not None:
            exclusion_mask_path = find_matching_mask(exclusion_root, case_id, timepoint=exclusion_timepoint)
            if exclusion_mask_path is None:
                print(f"[Warning] No exclusion mask found for {case_id}. Skipping.")
                continue
        else:
            exclusion_mask_path = None

        case_output_root = output_root / case_id
        for roi_image_path in roi_image_paths:
            output_path = clean_roi_mask_file(
                roi_mask_path=roi_image_path,
                allowed_mask_paths=allowed_mask_paths,
                forbidden_mask_paths=forbidden_mask_paths,
                output_root=case_output_root,
                exclusion_mask_path=exclusion_mask_path,
                exclusion_dilation=exclusion_dilation,
                suffix=suffix,
                overwrite_existing=overwrite_existing,
            )
            created_files.append(output_path)

    return created_files

