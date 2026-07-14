from pathlib import Path
import SimpleITK as sitk

from mri_pipeline.utils.files import build_output_path, ensure_dir


def run_n4_bias_correction(input_path, output_path=None):
    input_path = Path(input_path)

    if output_path is None:
        output_path = build_output_path(input_path, "_corr")
    else:
        output_path = Path(output_path)

    ensure_dir(output_path.parent)

    raw_img = sitk.ReadImage(str(input_path), sitk.sitkFloat64)

    head_mask = sitk.OtsuThreshold(raw_img, 0, 1, 200)
    head_mask = sitk.BinaryDilate(head_mask, [1, 1, 1])

    shrink_factor = 4
    input_small = sitk.Shrink(raw_img, [shrink_factor] * 3)
    mask_small = sitk.Shrink(head_mask, [shrink_factor] * 3)

    corrector = sitk.N4BiasFieldCorrectionImageFilter()
    corrector.SetMaximumNumberOfIterations([50, 40, 30])
    corrector.SetConvergenceThreshold(0.0001)
    corrector.SetBiasFieldFullWidthAtHalfMaximum(0.15)
    corrector.SetWienerFilterNoise(0.01)

    corrector.Execute(input_small, mask_small)

    log_bias_field = corrector.GetLogBiasFieldAsImage(raw_img)
    log_bias_field = sitk.Cast(log_bias_field, raw_img.GetPixelID())

    bias_field = sitk.Exp(log_bias_field)
    corrected_img = sitk.Divide(raw_img, bias_field)

    sitk.WriteImage(corrected_img, str(output_path))

    return output_path