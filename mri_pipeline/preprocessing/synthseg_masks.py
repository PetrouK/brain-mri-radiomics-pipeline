from pathlib import Path
import os
import shutil
import subprocess
import SimpleITK as sitk

import nibabel as nib
import numpy as np

from mri_pipeline.utils.files import ensure_dir, is_nifti, strip_nifti_extension


REGION_LABELS = {
    "ventricles": [4, 5, 14, 15, 43, 44],
    "csf": [24],
    "white-matter": [2, 41, 7, 8, 46, 47],
    "cerebellum": [7, 8, 46, 47],
}

REGION_SUFFIXES = {
    "ventricles": "_ventricles_mask.nii.gz",
    "csf": "_CSF_mask.nii.gz",
    "white-matter": "_wm_mask.nii.gz",
    "cerebellum": "_cerebellum_mask.nii.gz",
}

EXCLUDE_IMAGE_TOKENS = (
    "_mask",
    "_seg",
    "_segmap",
    "_synthseg",
    "_wm",
    "_diff",
    "z-score",
    "min-max",
    "fcm",
    "whitestripe",
)

def is_synthseg_candidate(path):
    path = Path(path)
    name = path.name.lower()

    if not is_nifti(path):
        return False

    if any(token in name for token in EXCLUDE_IMAGE_TOKENS):
        return False

    return True


def is_registered_pre_skullstrip_image(path):
    path = Path(path)
    name = path.name.lower()
    stem = strip_nifti_extension(path).lower()

    if not is_synthseg_candidate(path):
        return False

    if stem.endswith("_brain") or stem.endswith("_brain_bet") or stem.endswith("_bet"):
        return False

    return name.endswith("_r.nii") or name.endswith("_r.nii.gz")


def build_synthseg_command(
    script_path,
    input_path,
    output_path,
    python_executable="python",
    keepgeom=True,
    v1=False,
):
    cmd = [
        python_executable,
        str(script_path),
        "--i",
        str(input_path),
        "--o",
        str(output_path),
    ]

    if keepgeom:
        cmd.append("--keepgeom")

    if v1:
        cmd.append("--v1")

    return cmd


def resolve_synthseg_v1_flag(script_path, version="auto"):
    script_path = Path(script_path)
    synthseg_root = script_path.parents[2]
    models_dir = synthseg_root / "models"

    if str(version) == "1":
        if not (models_dir / "synthseg_1.0.h5").exists():
            raise FileNotFoundError(f"SynthSeg 1.0 model not found: {models_dir / 'synthseg_1.0.h5'}")
        return True

    if str(version) == "2":
        if not (models_dir / "synthseg_2.0.h5").exists():
            raise FileNotFoundError(f"SynthSeg 2.0 model not found: {models_dir / 'synthseg_2.0.h5'}")
        return False

    if str(version).lower() != "auto":
        raise ValueError("SynthSeg version must be 'auto', '1', or '2'.")

    if (models_dir / "synthseg_2.0.h5").exists():
        return False

    if (models_dir / "synthseg_1.0.h5").exists():
        return True

    raise FileNotFoundError(
        f"No SynthSeg model found in {models_dir}. Expected synthseg_2.0.h5 or synthseg_1.0.h5."
    )


def build_synthseg_env(python_executable):
    env = os.environ.copy()
    python_executable = Path(python_executable)
    if python_executable.parent.name.lower() in {"bin", "scripts"}:
        env_root = python_executable.parent.parent
    else:
        env_root = python_executable.parent
    env_library_bin = env_root / "Library" / "bin"

    if env_library_bin.exists():
        env["PATH"] = f"{env_library_bin}{os.pathsep}{env.get('PATH', '')}"

    return env


def get_case_info_from_image(image_path, input_root, timepoint_names=("Pre", "Post")):
    image_path = Path(image_path)
    input_root = Path(input_root)

    parent = image_path.parent
    timepoint_lookup = {name.lower(): name for name in timepoint_names}

    if parent.name.lower() in timepoint_lookup:
        case_id = parent.parent.name
        timepoint = timepoint_lookup[parent.name.lower()]
    elif parent.parent.name.lower() in timepoint_lookup:
        case_id = parent.name
        timepoint = timepoint_lookup[parent.parent.name.lower()]
    elif parent == input_root:
        case_id = strip_nifti_extension(image_path)
        timepoint = None
    else:
        case_id = parent.name
        timepoint = None

    return case_id, timepoint

def find_synthseg_input_images(input_root, patterns=None, timepoint_names=("Pre", "Post"), registered_only=False):
    input_root = Path(input_root)

    if patterns is None:
        patterns = ["*.nii", "*.nii.gz"]

    if input_root.is_file():
        if not is_nifti(input_root):
            raise ValueError(f"Not a Nifti file: {input_root}")
        is_candidate = (
            is_registered_pre_skullstrip_image(input_root)
            if registered_only
            else is_synthseg_candidate(input_root)
        )
        if not is_candidate:
            raise ValueError(f"Not a synthseg candidate: {input_root}")

        case_id, timepoint = get_case_info_from_image(
            image_path=input_root,
            input_root=input_root.parent,
            timepoint_names=timepoint_names,
        )
        return [(case_id, timepoint, input_root)]

    if not input_root.exists() or not input_root.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_root}")

    candidate_images = []
    seen = set()

    for pattern in patterns:
        for file in input_root.rglob(pattern):
            if file in seen:
                continue
            seen.add(file)

            if not file.is_file() or file.name.startswith("."):
                continue
            is_candidate = (
                is_registered_pre_skullstrip_image(file)
                if registered_only
                else is_synthseg_candidate(file)
            )
            if not is_candidate:
                continue

            case_id, timepoint = get_case_info_from_image(
                image_path=file,
                input_root=input_root,
                timepoint_names=timepoint_names,
            )
            candidate_images.append((case_id, timepoint, file))

    return sorted(candidate_images, key=lambda item: str(item[2]))

def stage_synthseg_batch_inputs(synthseg_inputs, staging_input_dir):
    staging_input_dir = ensure_dir(staging_input_dir)
    mapping = {}

    for index, (case_id, timepoint, image_path) in enumerate(synthseg_inputs, start=1):
        image_path = Path(image_path)
        staged_case_id = f"synthseg_case_{index:06d}"
        image_suffix = ".nii.gz" if image_path.name.lower().endswith(".nii.gz") else ".nii"
        staged_image_path = staging_input_dir / f"{staged_case_id}{image_suffix}"

        shutil.copy2(image_path, staged_image_path)

        mapping[staged_case_id] = {
            "case_id": case_id,
            "timepoint": timepoint,
            "image_path": image_path,
            "original_stem": strip_nifti_extension(image_path),
            "staged_image_path": staged_image_path,
            "staged_output_path": staging_input_dir.parent / "output" / f"{staged_case_id}_synthseg{image_suffix}",
        }

    return mapping



def extract_region_mask(synthseg_path, labels, output_path):
    synthseg_path = Path(synthseg_path)
    output_path = Path(output_path)

    seg_image = nib.load(str(synthseg_path))
    seg_data = seg_image.get_fdata().astype(np.int16)

    mask = np.isin(seg_data, labels).astype(np.uint8)
    mask_image = nib.Nifti1Image(mask, seg_image.affine, seg_image.header)
    mask_image.set_data_dtype(np.uint8)

    ensure_dir(output_path.parent)
    nib.save(mask_image, str(output_path))

    return output_path


def resample_mask_to_reference(mask_path, reference_image_path, output_path):
    mask_path = Path(mask_path)
    reference_image_path = Path(reference_image_path)
    output_path = Path(output_path)

    mask_image = sitk.ReadImage(str(mask_path), sitk.sitkUInt8)
    reference_image = sitk.ReadImage(str(reference_image_path), sitk.sitkFloat32)

    resampled_mask = sitk.Resample(
        mask_image,
        reference_image,
        sitk.Transform(3, sitk.sitkIdentity),
        sitk.sitkNearestNeighbor,
        0,
        sitk.sitkUInt8,
    )

    ensure_dir(output_path.parent)
    sitk.WriteImage(resampled_mask, str(output_path))

    return output_path


def create_synthseg_masks(
    input_root,
    synthseg_root,
    output_roots,
    regions=None,
    patterns=None,
    python_executable="python",
    script_path=None,
    keepgeom=True,
    v1=False,
    version="auto",
    resample_to_input=True,
    registered_only=False,
    timepoint_names=("Pre", "Post"),
):

    if script_path is None:
        raise ValueError("SynthSeg script_path is required.")

    script_path = Path(script_path)

    if not script_path.exists():
        raise FileNotFoundError(f"SynthSeg script not found: {script_path}")

    v1 = resolve_synthseg_v1_flag(script_path, version=version)

    input_root = Path(input_root)
    synthseg_root = Path(synthseg_root)

    if regions is None:
        regions = list(REGION_LABELS)

    if patterns is None:
        patterns = ["*.nii", "*.nii.gz"]

    unknown_regions = sorted(set(regions) - set(REGION_LABELS))
    if unknown_regions:
        raise ValueError(f"Unsupported SynthSeg regions: {unknown_regions}")

    if not input_root.exists():
        raise FileNotFoundError(f"Input path not found: {input_root}")

    created_files = []
    synthseg_inputs = find_synthseg_input_images(
        input_root=input_root,
        patterns=patterns,
        timepoint_names=timepoint_names,
        registered_only=registered_only,
    )

    print(f"{len(synthseg_inputs)} SynthSeg input images found.")

    if not synthseg_inputs:
        return created_files

    staging_input_dir = synthseg_root / "input"
    staging_output_dir = synthseg_root / "output"
    shutil.rmtree(staging_input_dir, ignore_errors=True)
    shutil.rmtree(staging_output_dir, ignore_errors=True)
    staging_output_dir = ensure_dir(staging_output_dir)
    mapping = stage_synthseg_batch_inputs(
        synthseg_inputs=synthseg_inputs,
        staging_input_dir=staging_input_dir,
    )

    cmd = build_synthseg_command(
        script_path=script_path,
        input_path=staging_input_dir,
        output_path=staging_output_dir,
        python_executable=python_executable,
        keepgeom=keepgeom,
        v1=v1,
    )
    subprocess.run(cmd, check=True, env=build_synthseg_env(python_executable))

    for staged_case_id, info in mapping.items():
        case_id = info["case_id"]
        timepoint = info["timepoint"]
        image_path = info["image_path"]
        original_stem = info["original_stem"]
        synthseg_path = info["staged_output_path"]
        case_label = f"{case_id}/{timepoint}" if timepoint is not None else case_id

        print(f"SynthSeg masks: {case_label}/{image_path.name}")

        if not synthseg_path.exists():
            raise FileNotFoundError(f"SynthSeg output not found: {synthseg_path}")

        for region in regions:
            region_output_root = output_roots.get(region)
            if region_output_root is None:
                print(f"  [Warning] No output root configured for region: {region}")
                continue

            output_dir = Path(region_output_root) / case_id
            if timepoint is not None:
                output_dir = output_dir / timepoint

            output_path = output_dir / f"{original_stem}{REGION_SUFFIXES[region]}"

            if output_path.exists():
                print(f"  [Skip] Mask exists: {output_path.name}")
                created_file = output_path
            else:
                created_file = extract_region_mask(
                    synthseg_path=synthseg_path,
                    labels=REGION_LABELS[region],
                    output_path=output_path,
                )
                print(f"  -> Created {region}: {created_file}")

            if resample_to_input:
                created_file = resample_mask_to_reference(
                    mask_path=created_file,
                    reference_image_path=image_path,
                    output_path=output_path,
                )
                print(f"  -> Resampled {region} to input geometry: {created_file}")

            created_files.append(created_file)

    return created_files

def create_white_matter_masks(
        input_root,
        output_root,
        synthseg_work_root,
        python_executable="python",
        script_path=None,
        keepgeom=True,
        v1=False,
        version="auto",
        resample_to_input=True,
        keep_intermediate=False,
        registered_only=False,
    ):
    
    input_root = Path(input_root)
    output_root = Path(output_root)

    output_root = ensure_dir(output_root)
    wm_output_root = ensure_dir(output_root / "Masks" / "White_Matter")

    created_files = create_synthseg_masks(
        input_root=input_root,
        synthseg_root=synthseg_work_root,
        output_roots={"white-matter": wm_output_root},
        regions=["white-matter"],
        patterns=None,
        python_executable=python_executable,
        script_path=script_path,
        keepgeom=keepgeom,
        v1=v1,
        version=version,
        resample_to_input=resample_to_input,
        registered_only=registered_only,
        timepoint_names=("Pre", "Post"),
    )

    if not keep_intermediate:
        shutil.rmtree(synthseg_work_root, ignore_errors=True)

    return created_files
