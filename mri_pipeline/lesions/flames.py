import os
from pathlib import Path
import shutil
import subprocess

from mri_pipeline.utils.files import ensure_dir, get_patient_dirs, is_nifti, list_nifti_files, strip_nifti_extension

NORMALIZATION_TOKENS = ("z-score", "min-max", "fcm", "whitestripe")


def stage_flames_input(image_path, staging_input_dir):
    image_path = Path(image_path)

    if not image_path.exists() or not image_path.is_file() or not is_nifti(image_path):
        raise ValueError(f"File doesn't exist or is not nifti: {image_path}")

    staging_input_dir = ensure_dir(staging_input_dir)

    case_id = strip_nifti_extension(image_path)
    staged_image = staging_input_dir / f"{case_id}_0000.nii.gz"
    shutil.copy2(image_path, staged_image)

    return staged_image


def get_flames_output_mask(staging_output_dir, image_path):
    staging_output_dir = Path(staging_output_dir)
    case_id = strip_nifti_extension(image_path)

    expected_mask_path = staging_output_dir / f"{case_id}.nii.gz"

    return expected_mask_path


def run_flames_prediction(
    staging_input_dir,
    staging_output_dir,
    dataset_id="004",
    configuration="3d_fullres",
    trainer="nnUNetTrainer_8000epochs",
    flames_root=None,
):
    
    env = os.environ.copy()

    if flames_root is not None:
        flames_root = Path(flames_root)
        env["nnUNet_raw"] = str(flames_root / "nnUNet_raw")
        env["nnUNet_preprocessed"] = str(flames_root / "nnUNet_preprocessed")
        env["nnUNet_results"] = str(flames_root / "nnUNet_results")

    staging_input_dir = ensure_dir(staging_input_dir)
    staging_output_dir = ensure_dir(staging_output_dir)

    command = [
        "nnUNetv2_predict",
        "-i",
        str(staging_input_dir),
        "-o",
        str(staging_output_dir),
        "-d",
        dataset_id,
        "-c",
        configuration,
        "-tr",
        trainer,
    ]

    subprocess.run(command, check=True, env=env)

    return staging_output_dir


def find_pre_flair_for_flames(pre_folder):
    pre_folder = Path(pre_folder)
    files = list_nifti_files(pre_folder)
    matches = []

    for file in files:
        name = file.name.lower()

        if not name.endswith("_brain.nii.gz"):
            continue

        if "_bet" in name:
            continue

        if any(token in name for token in NORMALIZATION_TOKENS):
            continue

        matches.append(file)

    return sorted(matches)[0] if matches else None

def copy_flames_segmap(raw_mask_path, final_output_dir, image_path):
    raw_mask_path = Path(raw_mask_path)
    if not raw_mask_path.exists() or not raw_mask_path.is_file() or not is_nifti(raw_mask_path):
        raise ValueError(f"File doesn't exist or is not nifti: {raw_mask_path}")

    final_output_dir = ensure_dir(final_output_dir)

    case_id = strip_nifti_extension(image_path)

    output_path = final_output_dir / f"{case_id}_segmap.nii.gz"

    shutil.copy2(raw_mask_path, output_path)

    return output_path

def segment_lesions_file(image_path, output_root, lesion_folder="Existing_Pre", case_folder_name=None, flames_root=None):
    output_root = Path(output_root)
    
    staging_input = output_root / "FLAMeS_Work" / "input"
    staging_output = output_root / "FLAMeS_Work" / "output"

    final_output_root = output_root / "Lesions" / lesion_folder

    if case_folder_name is not None:
        final_output_root = final_output_root / str(case_folder_name)

    stage_flames_input(image_path, staging_input)
    run_flames_prediction(
        staging_input_dir=staging_input,
        staging_output_dir=staging_output,
        flames_root=flames_root,
    )

    mask_path = get_flames_output_mask(staging_output, image_path)
    final_mask_path = copy_flames_segmap(mask_path, final_output_root, image_path)
    shutil.rmtree(staging_input, ignore_errors=True)
    shutil.rmtree(staging_output, ignore_errors=True)

    return final_mask_path

def segment_pre_lesions_file(image_path, output_root, case_folder_name=None, flames_root=None):
    return segment_lesions_file(
        image_path=image_path,
        output_root=output_root,
        lesion_folder="Existing_Pre",
        case_folder_name=case_folder_name,
        flames_root=flames_root,
    )

def segment_pre_lesions_folder(preprocessed_root, output_root, pre_timepoint="Pre", flames_root=None):
    preprocessed_root = Path(preprocessed_root)
    output_root = Path(output_root)

    created_masks = []

    for case_folder in get_patient_dirs(preprocessed_root):
        case_folder_name = case_folder.name
        pre_folder = case_folder / pre_timepoint
        if not pre_folder.exists():
            pre_folder = case_folder

        image_path = find_pre_flair_for_flames(pre_folder)

        if image_path is None:
            print(f"[Warning] No skull-stripped Pre FLAIR found for {case_folder_name}. Skipping.")
            continue

        created_mask = segment_pre_lesions_file(
            image_path=image_path,
            output_root=output_root,
            case_folder_name=case_folder_name,
            flames_root=flames_root,
        )

        created_masks.append(created_mask)

    return created_masks

def segment_lesions_folder(input_root, output_root, lesion_folder="Existing_Pre", flames_root=None):
    input_root = Path(input_root)
    output_root = Path(output_root)

    created_masks = []
    for case_folder in get_patient_dirs(input_root):
        case_folder_name = case_folder.name

        image_path = find_pre_flair_for_flames(case_folder)
        if image_path is None:
            print(f"[Warning] No skull-stripped FLAIR found for {case_folder_name}. Skipping.")
            continue

        created_mask = segment_lesions_file(
            image_path=image_path,
            output_root=output_root,
            lesion_folder=lesion_folder,
            case_folder_name=case_folder_name,
            flames_root=flames_root,
        )

        created_masks.append(created_mask)

    return created_masks