from pathlib import Path
import shutil
import subprocess

import nibabel as nib
import numpy as np

from mri_pipeline.utils.files import ensure_dir


REGION_LABELS = {
    "ventricles": [4, 5, 14, 15, 43, 44],
    "csf": [24],
    "white-matter": [2, 41],
    "cerebellum": [7, 8, 46, 47],
}

REGION_SUFFIXES = {
    "ventricles": "_ventricles_mask.nii.gz",
    "csf": "_CSF_mask.nii.gz",
    "white-matter": "_wm_mask.nii.gz",
    "cerebellum": "_cerebellum_mask.nii.gz",
}


def build_synthseg_command(patient_work_dir, input_name, output_name, docker_image, use_gpu=True):
    cmd = ["docker", "run", "--rm"]

    if use_gpu:
        cmd += ["--gpus", "all"]

    cmd += [
        "-v",
        f"{Path(patient_work_dir).as_posix()}:/data",
        docker_image,
        "mri_synthseg",
        "--i",
        f"/data/{input_name}",
        "--o",
        f"/data/{output_name}",
        "--keepgeom",
    ]

    return cmd


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


def find_patient_images(patient_dir, patterns):
    patient_dir = Path(patient_dir)
    files = []

    for pattern in patterns:
        files.extend(patient_dir.glob(pattern))

    return sorted(
        path for path in files
        if path.is_file() and not path.name.startswith(".")
    )


def create_synthseg_masks(
    input_root,
    synthseg_root,
    output_roots,
    regions=None,
    patterns=None,
    docker_image="freesurfer/freesurfer:8.2.0",
    use_gpu=True,
):
    input_root = Path(input_root)
    synthseg_root = Path(synthseg_root)

    if regions is None:
        regions = list(REGION_LABELS)

    if patterns is None:
        patterns = ["*_corr_R_brain.nii", "*_corr_R_brain.nii.gz"]

    unknown_regions = sorted(set(regions) - set(REGION_LABELS))
    if unknown_regions:
        raise ValueError(f"Unsupported SynthSeg regions: {unknown_regions}")

    if not input_root.exists() or not input_root.is_dir():
        raise FileNotFoundError(f"Input folder not found: {input_root}")

    created_files = []
    patient_dirs = sorted(
        path for path in input_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )

    print(f"{len(patient_dirs)} patient folders found for SynthSeg masks.")

    for patient_dir in patient_dirs:
        patient_id = patient_dir.name
        patient_work_dir = ensure_dir(synthseg_root / patient_id)
        image_paths = find_patient_images(patient_dir, patterns)

        if not image_paths:
            print(f"[No file] {patient_id}: no matching brain image found.")
            continue

        for image_path in image_paths:
            print(f"SynthSeg masks: {patient_id}/{image_path.name}")

            stem = image_path.name.replace(".nii.gz", "").replace(".nii", "")
            copied_input = patient_work_dir / image_path.name
            synthseg_path = patient_work_dir / f"{stem}_synthseg_keepgeom.nii.gz"

            if not copied_input.exists():
                shutil.copy2(image_path, copied_input)

            if not synthseg_path.exists():
                cmd = build_synthseg_command(
                    patient_work_dir=patient_work_dir,
                    input_name=copied_input.name,
                    output_name=synthseg_path.name,
                    docker_image=docker_image,
                    use_gpu=use_gpu,
                )
                subprocess.run(cmd, check=True)
            else:
                print(f"  [Skip] SynthSeg exists: {synthseg_path.name}")

            for region in regions:
                region_output_root = output_roots.get(region)
                if region_output_root is None:
                    print(f"  [Warning] No output root configured for region: {region}")
                    continue

                output_path = (
                    Path(region_output_root)
                    / patient_id
                    / f"{stem}{REGION_SUFFIXES[region]}"
                )

                if output_path.exists():
                    print(f"  [Skip] Mask exists: {output_path.name}")
                    continue

                created_file = extract_region_mask(
                    synthseg_path=synthseg_path,
                    labels=REGION_LABELS[region],
                    output_path=output_path,
                )
                created_files.append(created_file)
                print(f"  -> Created {region}: {created_file}")

    return created_files
