import shutil
from pathlib import Path
from mri_pipeline.organize.split_sequences import transfer_file
from mri_pipeline.utils.files import ensure_dir, get_patient_dirs, list_nifti_files

try:
    from tqdm.auto import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable


def detect_normalization(path_or_name, normalizations):
    name = Path(path_or_name).name.lower()

    for norm in normalizations:
        if norm.lower() in name:
            return norm

    return None


def detect_timepoint(relative_path, pre_name="Pre", post_name="Post", default="Pre"):
    parts = [part.lower() for part in Path(relative_path).parts]

    if pre_name.lower() in parts:
        return pre_name

    if post_name.lower() in parts:
        return post_name

    return default


def is_final_brain_image(path):
    name = Path(path).name.lower()

    return "_brain" in name and "_bet" not in name


def choose_target_root(timepoint, target_root, pre_target_root=None, post_target_root=None):
    if timepoint.lower() == "pre" and pre_target_root is not None:
        return Path(pre_target_root)

    if timepoint.lower() == "post" and post_target_root is not None:
        return Path(post_target_root)

    if target_root is None:
        raise ValueError(f"No target root configured for {timepoint} files.")

    return Path(target_root)


def organize_by_normalization(
    source_root,
    target_root=None,
    normalizations=None,
    copy_files=False,
    pre_target_root=None,
    post_target_root=None,
    pre_name="Pre",
    post_name="Post",
):
    source_root = Path(source_root)
    target_root = None if target_root is None else Path(target_root)
    if not source_root.exists() or not source_root.is_dir():
        raise FileNotFoundError(f"Folder doesn't exist: {source_root}")

    if normalizations is None:
        normalizations = []
    
    created_files = []

    target_roots = []

    if pre_target_root is not None:
        target_roots.append(Path(pre_target_root))

    if post_target_root is not None:
        target_roots.append(Path(post_target_root))

    if target_root is not None:
        target_roots.append(target_root)

    for root in target_roots:
        ensure_dir(root)

        for norm in normalizations:
            ensure_dir(root / norm)

    if (source_root / pre_name).is_dir() or (source_root / post_name).is_dir():
        patients = [source_root]
    else:
        patients = get_patient_dirs(source_root)

    if not patients:
        root_files = list_nifti_files(source_root)
        if root_files:
            patients = [source_root]

    for patient_folder in tqdm(patients, desc="Split normalizations patients", unit="patient"):
        patient_id = patient_folder.name

        for file in list_nifti_files(patient_folder, recursive=True):
            norm = detect_normalization(file, normalizations)

            relative_file = file.relative_to(patient_folder)
            timepoint = detect_timepoint(
                relative_file,
                pre_name=pre_name,
                post_name=post_name,
                default=pre_name,
            )

            if norm is None:
                if not is_final_brain_image(file):
                    continue

                category = timepoint
            else:
                category = norm

            destination_root = choose_target_root(
                timepoint,
                target_root,
                pre_target_root=pre_target_root,
                post_target_root=post_target_root,
            )
            destination_file = destination_root / category / patient_id / file.name

            created_file = transfer_file(
                file,
                destination_file,
                copy_mode=copy_files,
            )
            created_files.append(created_file)

    return created_files



