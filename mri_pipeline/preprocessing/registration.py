from pathlib import Path
import SimpleITK as sitk

from mri_pipeline.utils.files import build_output_path, ensure_dir

def get_interpolator(interpolation):
    interpolation = interpolation.lower()

    interpolators = {
            "linear": sitk.sitkLinear,
            "cubic": sitk.sitkBSpline,
            "nearest": sitk.sitkNearestNeighbor
        }
    
    if interpolation not in interpolators:
        raise ValueError(f"Not a valid option: {interpolation}")

    return interpolators[interpolation]

def resample_image(reference_image, moving_image, transform, interpolation="linear", default_value=0.0):
    interpolator = get_interpolator(interpolation)

    resampled = sitk.Resample(
        moving_image,
        reference_image,
        transform,
        interpolator,
        default_value,
        moving_image.GetPixelID(),
    )

    return resampled

def apply_transform(reference_path, moving_path, transform_path, output_path=None, interpolation="linear"):
    reference_path = Path(reference_path)
    moving_path = Path(moving_path)
    transform_path = Path(transform_path)

    if output_path is None:
        output_path = build_output_path(moving_path, suffix= "_R")
    else:
        output_path = Path(output_path)

    print("  Applying transform:")
    print("   ref   :", reference_path)
    print("   moving:", moving_path)
    print("   tfm   :", transform_path)
    print("   out   :", output_path)

    ref_img = sitk.ReadImage(str(reference_path), sitk.sitkFloat32)
    moving_img = sitk.ReadImage(str(moving_path), sitk.sitkFloat32)
    transform = sitk.ReadTransform(str(transform_path))

    resampled = resample_image(ref_img, moving_img, transform, interpolation)

    ensure_dir(output_path.parent)
    sitk.WriteImage(resampled, str(output_path))
    print(f"Saved transformed image: {output_path}")
    return output_path

def estimate_transform(reference_path, moving_path, mask_path=None):
    reference_path = Path(reference_path)
    moving_path = Path(moving_path)

    ref_image = sitk.ReadImage(str(reference_path), sitk.sitkFloat64)
    moving_image = sitk.ReadImage(str(moving_path), sitk.sitkFloat64)

    initial_transform = sitk.CenteredTransformInitializer(
        ref_image,
        moving_image,
        sitk.AffineTransform(3),
        sitk.CenteredTransformInitializerFilter.GEOMETRY,
    )

    registration_method = sitk.ImageRegistrationMethod()

    registration_method.SetMetricAsMattesMutualInformation(
        numberOfHistogramBins=256
    )
    registration_method.SetMetricSamplingStrategy(
        registration_method.REGULAR
    )
    registration_method.SetMetricSamplingPercentage(0.25)

    if mask_path is not None:
        mask_path = Path(mask_path)
        mask_image = sitk.ReadImage(str(mask_path), sitk.sitkUInt8)
        registration_method.SetMetricFixedMask(mask_image)

    registration_method.SetInterpolator(sitk.sitkLinear)

    registration_method.SetOptimizerAsRegularStepGradientDescent(
        learningRate=2.0,
        minStep=1e-4,
        numberOfIterations=200,
        gradientMagnitudeTolerance=1e-6,
    )
    registration_method.SetOptimizerScalesFromPhysicalShift()

    registration_method.SetShrinkFactorsPerLevel(shrinkFactors=[4, 2, 1])
    registration_method.SetSmoothingSigmasPerLevel(smoothingSigmas=[2, 1, 0])
    registration_method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()

    registration_method.SetInitialTransform(initial_transform, inPlace=False)

    final_transform = registration_method.Execute(
        sitk.Cast(ref_image, sitk.sitkFloat64),
        sitk.Cast(moving_image, sitk.sitkFloat64),
    )

    return final_transform

def register_image(
    reference_path,
    moving_path,
    output_path=None,
    transform_path=None,
    save_transform_path=None,
    mask_path=None,
    interpolation="linear",
):
    reference_path = Path(reference_path)
    moving_path = Path(moving_path)

    if output_path is None:
        output_path = build_output_path(moving_path, "_R")
    else:
        output_path = Path(output_path)

    reference_image = sitk.ReadImage(str(reference_path), sitk.sitkFloat64)
    moving_image = sitk.ReadImage(str(moving_path), sitk.sitkFloat64)

    if transform_path is not None:
        transform_path = Path(transform_path)
        transform = sitk.ReadTransform(str(transform_path))
    else:
        transform = estimate_transform(
            reference_path=reference_path,
            moving_path=moving_path,
            mask_path=mask_path,
        )

        if save_transform_path is not None:
            save_transform_path = Path(save_transform_path)
            ensure_dir(save_transform_path.parent)
            sitk.WriteTransform(transform, str(save_transform_path))

    resampled = resample_image(
        reference_image=reference_image,
        moving_image=moving_image,
        transform=transform,
        interpolation=interpolation,
    )

    ensure_dir(output_path.parent)
    sitk.WriteImage(resampled, str(output_path))

    return output_path  


