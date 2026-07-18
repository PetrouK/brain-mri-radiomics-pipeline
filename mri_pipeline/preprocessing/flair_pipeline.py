from pathlib import Path
import shutil

from mri_pipeline.preprocessing.n4 import run_n4_bias_correction
from mri_pipeline.preprocessing.registration import register_image
from mri_pipeline.preprocessing.skull_strip import build_hdbet_mask_path, run_skull_stripping
from mri_pipeline.preprocessing.normalization import run_normalization
from mri_pipeline.preprocessing.diff_images import create_registered_difference_pair
from mri_pipeline.utils.files import (
    build_output_path,
    ensure_dir,
    get_patient_dirs,
    list_nifti_files,
    find_first_tfm,
    strip_nifti_extension,
)

try:
    from tqdm.auto import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable


def run_flair_pipeline(
    image_path,
    steps,
    reference_path=None,
    transform_path=None,
    save_transform_path=None,
    output_dir=None,
    mask_path=None,
    normalization_methods=None,
):
    image_path = Path(image_path)
    current_image = image_path
    explicit_mask_path = mask_path is not None
    current_mask = None if mask_path is None else Path(mask_path)

    if output_dir is not None:
        output_dir = Path(output_dir)
        ensure_dir(output_dir)

    if normalization_methods is None:
        normalization_methods = []

    normalized_steps = [step.lower() for step in steps]

    if "normalization" in normalized_steps and normalized_steps[-1] != "normalization":
        raise ValueError(
            "normalization must be the final preprocessing step because it creates output variants and does not update the main processing image."
        )

    results = {
        "input": image_path,
        "n4": None,
        "registered": None,
        "brain": None,
        "brain_mask": current_mask,
        "normalizations": {},
        "final_image": image_path,
    }

    for step_index, step in enumerate(tqdm(normalized_steps, desc=f"Steps: {image_path.name}", unit="step"), start=1):
        print(f"  Step {step_index}/{len(normalized_steps)}: {step}")

        if step == "n4":
            current_image = run_n4_bias_correction(
                current_image,
                output_path=None if output_dir is None else build_output_path(
                    current_image,
                    "_corr",
                    output_dir=output_dir,
                ),
            )
            results["n4"] = current_image

        elif step == "registration":
            if reference_path is None:
                raise ValueError("reference_path is required for registration step.")

            current_image = register_image(
                reference_path=reference_path,
                moving_path=current_image,
                output_path=None if output_dir is None else build_output_path(
                    current_image,
                    "_R",
                    output_dir=output_dir,
                ),
                transform_path=transform_path,
                save_transform_path=save_transform_path,
            )
            results["registered"] = current_image

        elif step == "skull-strip":
            brain_output_path = None if output_dir is None else build_output_path(
                current_image,
                "_brain",
                output_dir=output_dir,
                extension=".nii.gz",
            )
            current_image = run_skull_stripping(
                current_image,
                output_path=brain_output_path,
            )
            hdbet_mask = build_hdbet_mask_path(current_image)
            if not explicit_mask_path:
                current_mask = hdbet_mask
            results["brain"] = current_image
            results["brain_mask"] = hdbet_mask

        elif step == "normalization":
            for method in tqdm(normalization_methods, desc="Normalizations", unit="method", leave=False):
                normalized_path = run_normalization(
                    image_path=current_image,
                    method=method,
                    mask_path=current_mask,
                    output_path=None if output_dir is None else build_output_path(
                        current_image,
                        f"_{method.lower()}",
                        output_dir=output_dir,
                    ),
                )
                results["normalizations"][method] = normalized_path

        else:
            raise ValueError(f"Unsupported preprocessing step: {step}")

    results["final_image"] = current_image

    return results

def find_sequence_image(folder, sequence="FLAIR"):
    folder = Path(folder)
    sequence = sequence.lower()

    if not folder.exists() or not folder.is_dir():
        return None

    files = [
        path for path in list_nifti_files(folder, recursive=False)
        if sequence in path.name.lower()
    ]

    return files[0] if files else None

def build_registration_transform_path(transform_root, patient_id, image_path):
    image_path = Path(image_path)
    transform_root = Path(transform_root)

    transform_name = f"{strip_nifti_extension(image_path)}_R.tfm"

    return transform_root / patient_id / transform_name

def copy_transform_to_output(source_transform_path, output_transform_path):
    source_transform_path = Path(source_transform_path)
    output_transform_path = Path(output_transform_path)

    ensure_dir(output_transform_path.parent)
    shutil.copy2(source_transform_path, output_transform_path)

    return output_transform_path

def prepare_transform_for_image(output_transform_root, input_transform_root, patient_id, image_path):
    output_transform_path = build_registration_transform_path(
        output_transform_root,
        patient_id,
        image_path,
    )

    if output_transform_path.exists():
        return output_transform_path

    input_transform_path = find_patient_transform(input_transform_root, patient_id)

    if input_transform_path is not None:
        return copy_transform_to_output(input_transform_path, output_transform_path)

    return None

def find_patient_transform(transform_root, patient_id):
    if transform_root is None:
        return None

    transform_root = Path(transform_root)

    if not transform_root.exists() or not transform_root.is_dir():
        return None

    patient_transform_folder = transform_root / patient_id
    transform_path = find_first_tfm(patient_transform_folder)

    if transform_path is not None:
        return transform_path

    matching_files = sorted(
        path for path in transform_root.iterdir()
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.name.lower().endswith(".tfm")
            and patient_id.lower() in path.name.lower()
        )
    )

    return matching_files[0] if matching_files else None

def preprocess_flair_patient(
    patient_id,
    pre_image_path,
    post_image_path,
    atlas_path,
    output_root,
    pre_transform_path=None,
    post_transform_path=None,
    pre_save_transform_path=None,
    post_save_transform_path=None,
    diff_output_root=None,
    steps=None,
    normalization_methods=None,
):
    if steps is None:
        steps = ["n4", "registration", "skull-strip", "normalization"]

    if normalization_methods is None:
        normalization_methods = []

    normalized_steps = [step.lower() for step in steps]
    image_steps = [step for step in normalized_steps if step != "diff"]
    run_diff = "diff" in normalized_steps

    output_root = Path(output_root)
    patient_output_root = ensure_dir(output_root / patient_id)

    results = {
        "patient_id": patient_id,
        "pre": None,
        "post": None,
    }

    pre_output_dir = ensure_dir(patient_output_root / "Pre")

    results["pre"] = run_flair_pipeline(
        image_path=pre_image_path,
        steps=image_steps,
        reference_path=atlas_path,
        transform_path=pre_transform_path,
        save_transform_path=pre_save_transform_path,
        output_dir=pre_output_dir,
        normalization_methods=normalization_methods,
    )

    if post_image_path is None:
        return results

    post_reference_path = results["pre"].get("registered")

    if post_reference_path is None:
        post_reference_path = results["pre"]["final_image"]

    post_output_dir = ensure_dir(patient_output_root / "Post")

    results["post"] = run_flair_pipeline(
        image_path=post_image_path,
        steps=image_steps,
        reference_path=post_reference_path,
        transform_path=post_transform_path,
        save_transform_path=post_save_transform_path,
        output_dir=post_output_dir,
        normalization_methods=normalization_methods,
    )
    
    if run_diff:
        if diff_output_root is None:
            diff_output_root = output_root.parent / "Difference_Images"

        pre_diff_image = results["pre"].get("brain") or results["pre"].get("registered") or results["pre"]["final_image"]
        post_diff_image = results["post"].get("brain") or results["post"].get("registered") or results["post"]["final_image"]

        results["diff"] = create_registered_difference_pair(
            reference_path=pre_diff_image,
            source_path=post_diff_image,
            output_root=Path(diff_output_root) / patient_id,
            register_if_needed=False,
        )

    return results

def preprocess_flair_folder(
    input_root,
    output_root,
    atlas_path,
    pre_transform_root=None,
    post_transform_root=None,
    input_pre_transform_root=None,
    input_post_transform_root=None,
    diff_output_root=None,
    timepoints=None,
    sequence="FLAIR",
    steps=None,
    normalization_methods=None,
    save_transforms=True,
    overwrite_transforms=False,
):
    input_root = Path(input_root)

    if timepoints is None:
        timepoints = {"pre": "Pre", "post": "Post"}

    pre_folder_name = timepoints.get("pre", "Pre")
    post_folder_name = timepoints.get("post", "Post")

    if input_pre_transform_root is None:
        input_pre_transform_root = input_root / "Transforms" / pre_folder_name

    if input_post_transform_root is None:
        input_post_transform_root = input_root / "Transforms" / post_folder_name

    if (input_root / pre_folder_name).is_dir() or (input_root / post_folder_name).is_dir():
        patient_folders = [input_root]
    else:
        patient_folders = get_patient_dirs(input_root)

    if not patient_folders:
        root_files = list_nifti_files(input_root)
        if root_files:
            patient_folders = [input_root]
    results = []

    print(f"{len(patient_folders)} patient folders found.")

    for patient_index, patient_folder in enumerate(
        tqdm(patient_folders, desc="FLAIR patients", unit="patient"),
        start=1,
    ):
        patient_id = patient_folder.name
        print(f"Patient {patient_index}/{len(patient_folders)} preprocessing: {patient_id}")

        pre_folder = patient_folder / pre_folder_name
        if not pre_folder.exists() or not pre_folder.is_dir():
            pre_folder = patient_folder
        post_folder = patient_folder / post_folder_name

        pre_image_path = find_sequence_image(pre_folder, sequence=sequence)
        post_image_path = find_sequence_image(post_folder, sequence=sequence)

        if pre_image_path is None:
            print(f"  [Warning] No {sequence} Pre image found for {patient_id}. Skipping.")
            continue

        if post_image_path is None:
            print(f"  [Warning] No {sequence} Post image found for {patient_id}. Only Pre will be processed.")

        pre_save_transform_path = None
        post_save_transform_path = None

        if save_transforms and pre_transform_root is not None:
            pre_save_transform_path = build_registration_transform_path(
                pre_transform_root,
                patient_id,
                pre_image_path,
            )

        if save_transforms and post_transform_root is not None and post_image_path is not None:
            post_save_transform_path = build_registration_transform_path(
                post_transform_root,
                patient_id,
                post_image_path,
            )
        if overwrite_transforms:
            pre_transform_path = None
            post_transform_path = None
        else:
            pre_transform_path = prepare_transform_for_image(
                output_transform_root=pre_transform_root,
                input_transform_root=input_pre_transform_root,
                patient_id=patient_id,
                image_path=pre_image_path,
            )

            if post_image_path is not None:
                post_transform_path = prepare_transform_for_image(
                    output_transform_root=post_transform_root,
                    input_transform_root=input_post_transform_root,
                    patient_id=patient_id,
                    image_path=post_image_path,
                )
            else:
                post_transform_path = None
        patient_results = preprocess_flair_patient(
            patient_id=patient_id,
            pre_image_path=pre_image_path,
            post_image_path=post_image_path,
            atlas_path=atlas_path,
            output_root=output_root,
            pre_transform_path=pre_transform_path,
            post_transform_path=post_transform_path,
            pre_save_transform_path=pre_save_transform_path,
            post_save_transform_path=post_save_transform_path,
            diff_output_root=diff_output_root,
            steps=steps,
            normalization_methods=normalization_methods,
        )

        results.append(patient_results)

    return results
