from pathlib import Path

import numpy as np
import SimpleITK as sitk

from mri_pipeline.utils.files import ensure_dir


def find_brain_image(folder, pattern="*_brain.nii*"):
    folder = Path(folder)

    if not folder.exists() or not folder.is_dir():
        return None

    matches = sorted(
        path for path in folder.glob(pattern)
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.name.lower().endswith((".nii", ".nii.gz"))
        )
    )

    if len(matches) > 1:
        print(f"[Warning] Multiple brain images found in {folder}. Using: {matches[0].name}")

    return matches[0] if matches else None


def create_histogram_matched_difference(
    source_path,
    reference_path,
    output_path,
    histogram_levels=256,
    match_points=10,
):
    source_path = Path(source_path)
    reference_path = Path(reference_path)
    output_path = Path(output_path)

    source_image = sitk.ReadImage(str(source_path), sitk.sitkFloat32)
    reference_image = sitk.ReadImage(str(reference_path), sitk.sitkFloat32)

    if source_image.GetSize() != reference_image.GetSize():
        raise ValueError(
            "Images must have the same size for difference image creation. "
            f"Source: {source_image.GetSize()}, reference: {reference_image.GetSize()}"
        )

    matcher = sitk.HistogramMatchingImageFilter()
    matcher.SetNumberOfHistogramLevels(histogram_levels)
    matcher.SetNumberOfMatchPoints(match_points)
    matcher.ThresholdAtMeanIntensityOn()

    matched_image = matcher.Execute(source_image, reference_image)

    matched_data = sitk.GetArrayFromImage(matched_image)
    reference_data = sitk.GetArrayFromImage(reference_image)

    mask = reference_data != 0
    difference_data = np.zeros_like(reference_data, dtype=np.float32)
    difference_data[mask] = np.abs(matched_data[mask] - reference_data[mask])

    difference_image = sitk.GetImageFromArray(difference_data)
    difference_image.CopyInformation(reference_image)

    ensure_dir(output_path.parent)
    sitk.WriteImage(difference_image, str(output_path))

    return output_path


def create_flair_difference_images(
    pre_root,
    post_root,
    output_root,
    brain_pattern="*_brain.nii*",
):
    pre_root = Path(pre_root)
    post_root = Path(post_root)
    output_root = Path(output_root)

    if not pre_root.exists() or not pre_root.is_dir():
        raise FileNotFoundError(f"Pre FLAIR folder not found: {pre_root}")

    if not post_root.exists() or not post_root.is_dir():
        raise FileNotFoundError(f"Post FLAIR folder not found: {post_root}")

    created_files = []
    patient_folders = sorted(
        path for path in pre_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )

    print(f"{len(patient_folders)} Pre patient folders found.")

    for pre_patient_folder in patient_folders:
        patient_id = pre_patient_folder.name
        post_patient_folder = post_root / patient_id

        print(f"Difference image: {patient_id}")

        if not post_patient_folder.exists() or not post_patient_folder.is_dir():
            print(f"  [Warning] No Post folder found for {patient_id}. Skipping.")
            continue

        pre_image = find_brain_image(pre_patient_folder, pattern=brain_pattern)
        post_image = find_brain_image(post_patient_folder, pattern=brain_pattern)

        if pre_image is None:
            print(f"  [Warning] No Pre brain image found for {patient_id}. Skipping.")
            continue

        if post_image is None:
            print(f"  [Warning] No Post brain image found for {patient_id}. Skipping.")
            continue

        output_path = output_root / patient_id / f"{patient_id}_diff.nii"

        try:
            created_file = create_histogram_matched_difference(
                source_path=pre_image,
                reference_path=post_image,
                output_path=output_path,
            )
        except Exception as exc:
            print(f"  [Error] Failed for {patient_id}: {exc}")
            continue

        created_files.append(created_file)
        print(f"  -> Created: {created_file}")

    return created_files
