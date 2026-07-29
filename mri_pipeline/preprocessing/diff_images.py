from pathlib import Path
from datetime import datetime

import numpy as np
import SimpleITK as sitk

from mri_pipeline.preprocessing.registration import register_image
from mri_pipeline.utils.files import ensure_dir, get_patient_dirs


def is_nifti(path):
    name = Path(path).name.lower()

    return name.endswith((".nii", ".nii.gz"))


def strip_nifti_extension(path):
    name = Path(path).name
    lower_name = name.lower()

    if lower_name.endswith(".nii.gz"):
        return name[:-7]

    if lower_name.endswith(".nii"):
        return name[:-4]

    return Path(path).stem

def images_have_same_geometry(source_image, reference_image):
    return (
        source_image.GetSize() == reference_image.GetSize()
        and source_image.GetSpacing() == reference_image.GetSpacing()
        and source_image.GetOrigin() == reference_image.GetOrigin()
        and source_image.GetDirection() == reference_image.GetDirection()
    )

def save_image_copy(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)

    ensure_dir(output_path.parent)

    image = sitk.ReadImage(str(input_path))
    sitk.WriteImage(image, str(output_path))

    return output_path

def build_pair_output_dir(output_root):
    output_root = Path(output_root)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pair_dir = output_root / f"Pair_{timestamp}"
    ensure_dir(pair_dir)
    return pair_dir

def create_histogram_difference(
        source_path,
        reference_path,
        output_diff_path,
        histogram_levels=512,
        match_points=10,
        threshold_at_mean=True
    ):
    source_path = Path(source_path)
    reference_path = Path(reference_path)
    output_diff_path = Path(output_diff_path)

    source_image = sitk.ReadImage(str(source_path), sitk.sitkFloat32)
    reference_image = sitk.ReadImage(str(reference_path), sitk.sitkFloat32)

    if not images_have_same_geometry(source_image, reference_image):
        raise ValueError("Source and reference images do not have the same geometry. Register the source image before creating a difference image.")
    
    matcher = sitk.HistogramMatchingImageFilter()
    matcher.SetNumberOfHistogramLevels(histogram_levels)
    matcher.SetNumberOfMatchPoints(match_points)
    if threshold_at_mean:
        matcher.ThresholdAtMeanIntensityOn()

    matched_img = matcher.Execute(source_image, reference_image)

    matched_np = sitk.GetArrayFromImage(matched_img)
    reference_np = sitk.GetArrayFromImage(reference_image)

    mask = reference_np != 0
    diff_np = np.zeros_like(reference_np, dtype=np.float32)
    diff_np[mask] = np.abs(matched_np[mask] - reference_np[mask])

    diff_img = sitk.GetImageFromArray(diff_np)
    diff_img.CopyInformation(reference_image)
    
    ensure_dir(output_diff_path.parent)
    sitk.WriteImage(diff_img, str(output_diff_path))
    print(f"[OK] Saved difference image: {output_diff_path}")

    return output_diff_path

def create_registered_difference_pair(
        reference_path,
        source_path,
        output_root,
        histogram_levels=512,
        match_points=10,
        threshold_at_mean=True,
        register_if_needed=True,
    ):

    source_path = Path(source_path)
    reference_path = Path(reference_path)
    output_root = Path(output_root)

    pair_dir = build_pair_output_dir(output_root)

    reference_output = pair_dir / "reference.nii.gz"
    registered_source_output = pair_dir / "source_registered.nii.gz"
    difference_output = pair_dir / "difference.nii.gz"
    transform_output = pair_dir / "source_to_reference.tfm"

    save_image_copy(reference_path, reference_output)

    source_image = sitk.ReadImage(str(source_path), sitk.sitkFloat32)
    reference_image = sitk.ReadImage(str(reference_path), sitk.sitkFloat32)

    registration_applied = False
    if images_have_same_geometry(source_image, reference_image):
        save_image_copy(source_path, registered_source_output)
    else:
        if not register_if_needed:
            raise ValueError("Source and reference images do not have the same geometry. Register the source image before creating a difference image.")
        else:
            register_image(
                reference_path=reference_path,
                moving_path=source_path,
                output_path=registered_source_output,
                save_transform_path=transform_output,
            )
            registration_applied = True

    create_histogram_difference(
        source_path=registered_source_output,
        reference_path=reference_output,
        output_diff_path=difference_output,
        histogram_levels=histogram_levels,
        match_points=match_points,
        threshold_at_mean=threshold_at_mean,
    )

    return {
        "reference": reference_output,
        "source_registered": registered_source_output,
        "difference": difference_output,
        "transform": transform_output if registration_applied else None,
        "registration_applied": registration_applied,
    }



def find_difference_image(folder, brain_pattern="*_R_brain.nii*", registered_pattern="*_R.nii*"):
    folder = Path(folder)

    if not folder.exists() or not folder.is_dir():
        return None
    
    brain_matches = sorted(
        path for path in folder.glob(brain_pattern)
        if path.is_file()
        and is_nifti(path)
        and "_bet" not in path.name.lower()
    )
    registered_matches = sorted(
        path for path in folder.glob(registered_pattern)
        if path.is_file()
        and is_nifti(path)
        and "_brain" not in path.name.lower()
        and "_bet" not in path.name.lower()
    )
    if brain_matches:
        return brain_matches[0]
    if registered_matches:
        return registered_matches[0]
    
    return None

def create_flair_difference_images(
    preprocessed_root,
    output_root,
    pre_timepoint="Pre",
    post_timepoint="Post",
    histogram_levels=512,
    match_points=10,
    threshold_at_mean=True,
    register_missing=False,
    ):

    preprocessed_root = Path(preprocessed_root)
    output_root = Path(output_root)

    patients  = get_patient_dirs(preprocessed_root)

    results=[]
    for patient in patients:
        patient_id = patient.name
        pre_folder = patient / pre_timepoint
        post_folder = patient / post_timepoint

        pre_image = find_difference_image(pre_folder)
        post_image = find_difference_image(post_folder)

        if pre_image is None or post_image is None:
            print(
                f"[Warning] Difference image skipped for {patient_id}: "
                "registered Pre/Post images were not found."
            )
            continue
        
        output_patient_root = output_root / patient_id
        result = create_registered_difference_pair(
                reference_path=pre_image,
                source_path=post_image,
                output_root=output_patient_root,
                histogram_levels=histogram_levels,
                match_points=match_points,
                threshold_at_mean=threshold_at_mean,
                register_if_needed=register_missing
            )
        
        results.append(result)

    return results





    
