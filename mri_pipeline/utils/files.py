from pathlib import Path

def is_nifti(path):
    path = Path(path)
    name = path.name.lower()

    return name.endswith((".nii", ".nii.gz"))

def list_nifti_files(folder, recursive=False):
    folder = Path(folder)

    if not folder.exists() or not folder.is_dir():
        return []
    
    if recursive:
        nifti_files = [p for p in folder.rglob("*") if p.is_file() and is_nifti(p) and not p.name.startswith(".")]
    else:
        nifti_files = [p for p in folder.iterdir() if p.is_file() and is_nifti(p) and not p.name.startswith(".")]

    return sorted(nifti_files)

def find_first_nifti(folder):

    files = list_nifti_files(folder, recursive=False)

    return files[0] if files else None

def find_first_tfm(folder):
    folder = Path(folder)

    if not folder.is_dir():
        return None
    
    files = sorted([f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".") and f.name.lower().endswith(".tfm")])

    return files[0] if files else None

def ensure_dir(folder) -> Path:

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    return folder

def get_patient_dirs(path) -> list:
    path = Path(path)

    if not path.is_dir():
        return []

    folders = [f for f in path.iterdir() if f.is_dir() and not f.name.startswith(".")]

    return sorted(folders)

def strip_nifti_extension(path):
    path = Path(path)
    name = path.name
    lower_name = name.lower()

    if lower_name.endswith(".nii.gz"):
        return name[:-7]

    if lower_name.endswith(".nii"):
        return name[:-4]

    return path.stem

def build_output_path(input_path, suffix, output_dir=None, extension=None):
    input_path = Path(input_path)

    stem = strip_nifti_extension(input_path)
    name = input_path.name.lower()

    if extension is None:
        if name.endswith(".nii.gz"):
            extension = ".nii.gz"
        elif name.endswith(".nii"):
            extension = ".nii"
        else:
            extension = input_path.suffix

    new_filename = f"{stem}{suffix}{extension}"

    if output_dir is None:
        return input_path.parent / new_filename

    return Path(output_dir) / new_filename

