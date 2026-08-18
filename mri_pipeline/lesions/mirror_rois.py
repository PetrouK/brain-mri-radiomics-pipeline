from pathlib import Path

import SimpleITK as sitk

from mri_pipeline.utils.files import ensure_dir, build_output_path, get_patient_dirs
from mri_pipeline.lesions.mask_cleaning import find_matching_masks

def mirror_mask_left_right(input_path, output_path, axis=2):
    """
    Mirror a binary ROI mask left-right by flipping the x-axis of the
    SimpleITK numpy array. By default, SimpleITK arrays are [z, y, x].
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    image = sitk.ReadImage(str(input_path))
    image_array = sitk.GetArrayFromImage(image)
    mirrored_array = image_array.take(
        indices=range(image_array.shape[axis] - 1, -1, -1),
        axis=axis,
    )

    mirrored_image = sitk.GetImageFromArray(mirrored_array)
    mirrored_image.CopyInformation(image)
    mirrored_image = sitk.Cast(mirrored_image > 0, sitk.sitkUInt8)

    ensure_dir(output_path.parent)
    sitk.WriteImage(mirrored_image, str(output_path))

    return output_path


def build_mirrored_mask_path(input_mask_path, output_root, suffix="_mirrored"):
    input_mask_path = Path(input_mask_path)
    output_root = Path(output_root)

    output_path = build_output_path(input_path=input_mask_path, output_dir=output_root, suffix=suffix)

    return output_path

def mirror_mask_file(input_mask_path, output_root, suffix="_mirrored", axis=2, overwrite_existing=False):
    output_path = build_mirrored_mask_path(input_mask_path, output_root, suffix)

    if output_path.exists() and not overwrite_existing:
        print(f"[Skip] Mirrored mask already exists: {output_path}")
        return output_path

    return mirror_mask_left_right(input_mask_path, output_path, axis=axis)


def mirror_roi_masks_folder(roi_root, output_root, suffix="_mirrored", axis=2, overwrite_existing=False):
    roi_root = Path(roi_root)
    output_root = Path(output_root)

    created_files = []
    patients = get_patient_dirs(roi_root)

    for patient in patients:
        case_id = patient.name
        input_mask_paths = find_matching_masks(roi_root, case_id)
        if not input_mask_paths:
            print(f"[Warning] No ROI mask found for {case_id}. Skipping.")
            continue

        case_output_root = output_root / case_id
        for input_mask_path in input_mask_paths:
            created_mask = mirror_mask_file(
                input_mask_path,
                case_output_root,
                suffix,
                axis,
                overwrite_existing,
            )
            created_files.append(created_mask)

    return created_files


def mirror_roi_masks(input_path, output_root, suffix="_mirrored", axis=2, overwrite_existing=False):
    input_path = Path(input_path)
    output_root = Path(output_root)

    if input_path.is_file():
        created_mask = mirror_mask_file(
            input_mask_path=input_path,
            output_root=output_root,
            suffix=suffix,
            axis=axis,
            overwrite_existing=overwrite_existing,
        )
        return [created_mask]

    if input_path.is_dir():
        return mirror_roi_masks_folder(
            roi_root=input_path,
            output_root=output_root,
            suffix=suffix,
            axis=axis,
            overwrite_existing=overwrite_existing,
        )

    raise FileNotFoundError(f"Input path not found: {input_path}")
