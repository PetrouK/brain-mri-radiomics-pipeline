import torch
from pathlib import Path
from mri_pipeline.utils.files import build_output_path, ensure_dir
import subprocess

def choose_hdbet_device():
    if torch.cuda.is_available():
        device = "cuda"
    else:
        # If CUDA not available but MPS (Apple Silicon) is available
        if torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    return device

def build_hdbet_mask_path(output_path):
    return build_output_path(output_path, "_bet")

def run_skull_stripping(input_path, output_path=None, save_mask=True, device=None):
    input_path = Path(input_path)

    if output_path is None:
        output_path = build_output_path(input_path, "_brain")
    else:
        output_path = Path(output_path)

    if device is None:
        device = choose_hdbet_device()

    ensure_dir(output_path.parent)

    cmd = [
        "hd-bet",
        "-i",
        str(input_path),
        "-o",
        str(output_path),
        "-device",
        device,
    ]

    if save_mask:
        cmd.append("--save_bet_mask")

    subprocess.run(cmd, check=True)

    return output_path
