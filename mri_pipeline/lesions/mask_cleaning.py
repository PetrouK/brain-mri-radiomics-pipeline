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

def clean_roi_mask(roi_mask_path, allowed_mask_path, output_path, exclusion_mask_path=None, exclusion_dilation=1):
    output_path = Path(output_path)

    roi = read_binary_mask(roi_mask_path)
    allowed = read_binary_mask(allowed_mask_path)

    check_same_geometry(roi, allowed, "allowed mask")

    cleaned = roi & allowed

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
        allowed_mask_path,
        output_root,
        exclusion_mask_path=None,
        exclusion_dilation=1,
        suffix="_cleaned",
    ):

    roi_mask_path = Path(roi_mask_path)
    allowed_mask_path = Path(allowed_mask_path)
    output_root = Path(output_root)

    output_path = build_cleaned_mask_path(output_root, roi_mask_path, suffix)

    output_path = clean_roi_mask(
        roi_mask_path=roi_mask_path,
        allowed_mask_path=allowed_mask_path,
        output_path=output_path,
        exclusion_mask_path=exclusion_mask_path,
        exclusion_dilation=exclusion_dilation,
    )
    return output_path

def find_matching_mask(mask_root, case_id, pattern="*.nii*"):
    mask_root = Path(mask_root)
    case_folder = mask_root / str(case_id)

    if not case_folder.exists() or not case_folder.is_dir():
        return None

    matches = sorted(
        path for path in case_folder.glob(pattern)
        if path.is_file()
    )

    return matches[0] if matches else None

def clean_roi_masks_folder(
        roi_root,
        allowed_root,
        output_root,
        exclusion_root=None,
        exclusion_dilation=1,
        suffix="_cleaned",
    ):

    roi_root = Path(roi_root)
    allowed_root = Path(allowed_root)
    output_root = Path(output_root)
    exclusion_root = Path(exclusion_root) if exclusion_root is not None else None

    patients = get_patient_dirs(roi_root)
    created_files = []

    for patient in patients:

        case_id = patient.name
        roi_image_path = find_matching_mask(roi_root, case_id)
        allowed_mask_path = find_matching_mask(allowed_root, case_id)

        if roi_image_path is None:
            print(f"[Warning] No ROI mask found for {case_id}. Skipping.")
            continue

        if allowed_mask_path is None:
            print(f"[Warning] No allowed mask found for {case_id}. Skipping.")
            continue

        if exclusion_root is not None:
            exclusion_mask_path = find_matching_mask(exclusion_root, case_id)
            if exclusion_mask_path is None:
                print(f"[Warning] No exclusion mask found for {case_id}. Skipping.")
                continue
        else:
            exclusion_mask_path = None

        case_output_root = output_root / case_id
        output_path = clean_roi_mask_file(
            roi_mask_path=roi_image_path,
            allowed_mask_path=allowed_mask_path,
            output_root=case_output_root,
            exclusion_mask_path=exclusion_mask_path,
            exclusion_dilation=exclusion_dilation,
            suffix=suffix,
        )
        created_files.append(output_path)

    return created_files

