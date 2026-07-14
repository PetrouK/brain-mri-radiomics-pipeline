from pathlib import Path
import numpy as np
import nibabel as nib
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from mri_pipeline.utils.files import build_output_path, ensure_dir

def load_nifti_data(image_path):

    image = nib.load(str(image_path))
    data = image.get_fdata().astype(np.float32)
    return image, data

def save_nifti_data(data, reference_image, output_path):
    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    new_image = nib.Nifti1Image(
        data,
        reference_image.affine,
        reference_image.header,
    )

    nib.save(new_image, str(output_path))

    return output_path

def zscore_normalize(data, mask=None):
    if mask is not None:
        voxel_mask = mask > 0
    else:
        voxel_mask = data != 0

    relevant_data = data[voxel_mask]

    if relevant_data.size == 0:
        raise ValueError("No voxels found for z-score normalization.")

    mean = np.mean(relevant_data)
    std = np.std(relevant_data)

    if std == 0:
        raise ValueError("Standard deviation is zero; cannot apply z-score normalization.")

    normalized = np.zeros_like(data, dtype=np.float32)
    normalized[voxel_mask] = (data[voxel_mask] - mean) / std

    return normalized

def minmax_normalize(data, mask=None):
    if mask is not None:
        voxel_mask = mask > 0
    else:
        voxel_mask = data != 0

    relevant_data = data[voxel_mask]

    if relevant_data.size == 0:
        raise ValueError("No voxels found for min-max normalization.")

    min_value = np.min(relevant_data)
    max_value = np.max(relevant_data)

    if max_value == min_value:
        raise ValueError("Max and min are equal; cannot apply min-max normalization.")

    normalized = np.zeros_like(data, dtype=np.float32)
    normalized[voxel_mask] = (
        (data[voxel_mask] - min_value) / (max_value - min_value)
    )

    return normalized

def fcm_normalize(
    data,
    mask=None,
    n_clusters=3,
    target_cluster=2,
    m=2.0,
    epsilon=1e-5,
    max_iter=100,
):
    if target_cluster >= n_clusters:
        raise ValueError(
            f"Invalid target_cluster={target_cluster}. "
            f"With n_clusters={n_clusters}, use 0 to {n_clusters - 1}."
        )

    if m <= 1:
        raise ValueError("Fuzzy exponent m must be > 1.")

    if mask is not None:
        voxel_mask = mask > 0
    else:
        voxel_mask = data != 0

    relevant_data = data[voxel_mask].astype(np.float32)

    if relevant_data.size == 0:
        raise ValueError("No voxels found for FCM normalization.")

    values = relevant_data.reshape(-1, 1)
    n_voxels = values.shape[0]

    membership = np.random.rand(n_voxels, n_clusters).astype(np.float32)
    membership = membership / membership.sum(axis=1, keepdims=True)

    for _ in range(max_iter):
        previous_membership = membership.copy()

        membership_m = membership ** m

        centers = (
            np.sum(membership_m * values, axis=0)
            / np.sum(membership_m, axis=0)
        )

        distances = np.abs(values - centers.reshape(1, -1))
        distances = np.fmax(distances, 1e-10)

        power = 2.0 / (m - 1.0)
        inverse_distances = distances ** (-power)
        membership = inverse_distances / np.sum(
            inverse_distances,
            axis=1,
            keepdims=True,
        )

        change = np.linalg.norm(membership - previous_membership)

        if change < epsilon:
            break

    sorted_centers = np.sort(centers)
    target_value = sorted_centers[target_cluster]

    if target_value == 0:
        raise ValueError("Target FCM cluster center is zero; cannot normalize.")

    normalized = np.zeros_like(data, dtype=np.float32)
    normalized[voxel_mask] = data[voxel_mask] / target_value

    return normalized

def whitestripe_normalize(
    data,
    mask=None,
    sequence_type="flair",
    bins=2000,
    smoothing_sigma=10,
    width_fraction=0.05,
):
    if mask is not None:
        voxel_mask = mask > 0
    else:
        voxel_mask = data != 0

    relevant_data = data[voxel_mask].astype(np.float32)

    if relevant_data.size == 0:
        raise ValueError("No voxels found for WhiteStripe normalization.")

    hist, edges = np.histogram(relevant_data, bins=bins)
    smoothed_hist = gaussian_filter1d(hist, sigma=smoothing_sigma)

    peaks, _ = find_peaks(
        smoothed_hist,
        prominence=np.max(smoothed_hist) * 0.05,
    )

    if peaks.size == 0:
        raise ValueError("No histogram peaks found for WhiteStripe normalization.")

    bin_centers = (edges[:-1] + edges[1:]) / 2

    sequence_type = sequence_type.lower()

    if sequence_type == "t1":
        peak_index = peaks[-1]
    elif sequence_type == "flair":
        peak_index = peaks[np.argmax(smoothed_hist[peaks])]
    else:
        raise ValueError(f"Unsupported sequence_type: {sequence_type}")

    mu_ws = bin_centers[peak_index]

    width = abs(mu_ws) * width_fraction
    lower_bound = mu_ws - width
    upper_bound = mu_ws + width

    stripe_pixels = relevant_data[
        (relevant_data >= lower_bound) & (relevant_data <= upper_bound)
    ]

    if stripe_pixels.size == 0:
        raise ValueError("No voxels found inside the WhiteStripe range.")

    sigma_ws = np.std(stripe_pixels)

    if sigma_ws == 0:
        raise ValueError("WhiteStripe standard deviation is zero.")

    normalized = np.zeros_like(data, dtype=np.float32)
    normalized[voxel_mask] = (data[voxel_mask] - mu_ws) / sigma_ws

    return normalized

def run_normalization(
    image_path,
    method,
    mask_path=None,
    output_path=None,
    sequence_type="flair",
):
    image_path = Path(image_path)
    method = method.lower()

    image, data = load_nifti_data(image_path)

    mask = None
    if mask_path is not None:
        _, mask = load_nifti_data(mask_path)
        mask = mask.astype(np.uint8)

    if method == "z-score":
        normalized = zscore_normalize(data, mask=mask)
    elif method == "min-max":
        normalized = minmax_normalize(data, mask=mask)
    elif method == "fcm":
        normalized = fcm_normalize(data, mask=mask)
    elif method == "whitestripe":
        normalized = whitestripe_normalize(
            data,
            mask=mask,
            sequence_type=sequence_type,
        )
    else:
        raise ValueError(f"Unsupported normalization method: {method}")

    if output_path is None:
        output_path = build_output_path(image_path, f"_{method}")
    else:
        output_path = Path(output_path)

    return save_nifti_data(normalized, image, output_path)