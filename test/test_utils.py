from unittest import TestCase

import nibabel as nib
import numpy as np

from unet3d.utils.utils import resize, resize_affine, resample
from unet3d.utils.nilearn_custom_utils.nilearn_utils import crop_img, reorder_affine
from unet3d.utils.sitk_utils import resample_to_spacing


class TestUtils(TestCase):
    def _resize_image_test(self, image, target_shape):
        original_image_shape = image.shape
        new_image = resize(image, target_shape)
        self.assertEqual(new_image.shape, target_shape)
        new_image = resize(new_image, original_image_shape, interpolation="linear")
        self.assertEqual(new_image.shape, original_image_shape)

    def _create_image(self, image_shape):
        data = np.asarray(np.arange(np.prod(image_shape)).reshape(image_shape), dtype=np.float)
        affine = np.zeros((4, 4))
        np.fill_diagonal(affine, 1)
        return nib.Nifti1Image(data, affine)

    def test_resize_image_1(self):
        image_shape = (4, 4, 4)
        image = self._create_image(image_shape)
        new_size = (2, 2, 2)
        self._resize_image_test(image, new_size)

    def test_resize_image_2(self):
        self._resize_image_test(self._create_image((12, 10, 8)), (8, 8, 8))

    def test_resize_image_2d(self):
        data = np.arange(1, 5).reshape((2, 2))
        new_data = resample_to_spacing(data, (2, 2), (1, 1), interpolation="nearest")
        self.assertTrue(np.all(new_data == np.asarray([[1, 1, 2, 2],
                                                       [1, 1, 2, 2],
                                                       [3, 3, 4, 4],
                                                       [3, 3, 4, 4]])))
        orig_data = resample_to_spacing(new_data, (1, 1), (2, 2), interpolation="linear")
        self.assertTrue(np.all(data == orig_data))

    def test_resize_image_3(self):
        self._resize_image_test(self._create_image((2, 5, 3)), (7, 5, 11))

    def test_resize_image_3d(self):
        data = np.arange(1, 9).reshape((2, 2, 2))
        new_data = resample_to_spacing(data, (2, 2, 2), (1, 1, 1), interpolation="nearest")
        self.assertTrue(np.all(new_data[0] == np.asarray([[1, 1, 2, 2],
                                                          [1, 1, 2, 2],
                                                          [3, 3, 4, 4],
                                                          [3, 3, 4, 4]])))
        orig_data = resample_to_spacing(new_data, (1, 1, 1), (2, 2, 2), interpolation="linear")
        self.assertTrue(np.all(data == orig_data))

    def test_images_align(self):
        data = np.arange(1, 9).reshape((2, 2, 2))
        affine = np.diag(np.ones(4) * 2)
        affine[3, 3] = 1
        image_nib = nib.Nifti1Image(data, affine=affine)
        new_image_nib = resize(image_nib, (4, 4, 4), interpolation="nearest")
        self.assertTrue(np.all(new_image_nib.get_data()[0] == np.asarray([[1, 1, 2, 2],
                                                                          [1, 1, 2, 2],
                                                                          [3, 3, 4, 4],
                                                                          [3, 3, 4, 4]])))
        self.assertTrue(np.all(new_image_nib.affine == np.asarray([[1., 0., 0., -0.5],
                                                                   [0., 1., 0., -0.5],
                                                                   [0., 0., 1., -0.5],
                                                                   [0., 0., 0., 1.]])))
        original_image = resize(new_image_nib, (2, 2, 2), interpolation="nearest")
        self.assertTrue(np.all(image_nib.get_data() == original_image.get_data()))
        self.assertTrue(np.all(image_nib.affine == original_image.affine))

    def test_affine_crop(self):
        shape = (9, 9, 9)
        data = np.zeros(shape)
        data[3:6, 3:6, 3:6] = 1
        affine = np.diag(np.ones(len(shape) + 1))
        image = nib.Nifti1Image(data, affine)
        cropped_affine, cropped_shape = crop_img(image, return_affine=True, pad=False)
        expected_affine = np.copy(affine)
        expected_affine[:3, 3] = 3
        self.assertTrue(np.all(cropped_affine == expected_affine))

    def test_adjust_affine_spacing(self):
        old_shape = (128, 128, 128)
        new_shape = (64, 64, 64)
        old_affine = np.diag(np.ones(4))
        new_affine = resize_affine(old_affine, old_shape, new_shape)
        expected_affine = np.diag(np.ones(4) * 2)
        expected_affine[3, 3] = 1
        expected_affine[:3, 3] = 0.5
        np.testing.assert_array_equal(new_affine, expected_affine)

    def test_edge_resample(self):
        shape = (9, 9, 9)
        target_shape = shape
        data = np.ones(shape)
        data[-3:, -3:, -3:] = 2
        affine = np.diag(np.ones(4))
        image = nib.Nifti1Image(data, affine)
        cropped_affine, cropped_shape = crop_img(image, return_affine=True, percentile=50, pad=False)
        np.testing.assert_array_equal(cropped_shape, (3, 3, 3))
        np.testing.assert_array_almost_equal(np.ones(3)*6, cropped_affine[:3, 3])
        resized_affine = resize_affine(cropped_affine, cropped_shape, target_shape=target_shape)
        final_image = resample(image, resized_affine, target_shape, pad=True)
        np.testing.assert_array_equal(final_image.shape, target_shape)
        self.assertGreater(final_image.get_data().min(), 1)
        np.testing.assert_array_almost_equal(final_image.header.get_zooms(), np.ones(3)/(np.ones(3)*3))

    def test_crop_4d(self):
        shape = (9, 9, 9, 4)
        data = np.zeros(shape)
        data[3:6, 3:6, 3:6] = 1
        affine = np.diag(np.ones(4))
        image = nib.Nifti1Image(data, affine)
        cropped_image = crop_img(image, pad=False)
        expected_affine = np.copy(affine)
        expected_affine[:3, 3] = 3
        np.testing.assert_array_equal(cropped_image.affine, expected_affine)
        self.assertTrue(np.all(cropped_image.get_data() == 1))
        cropped_affine, cropped_shape = crop_img(image, pad=False, return_affine=True)
        np.testing.assert_array_equal(cropped_affine, expected_affine)

    def test_reorder_affine(self):
        affine = np.diag([-1, -3, 2, 1])
        affine[:3, 3] = [4, 6, 2]
        shape = (4, 4, 4)
        data = np.ones(shape)
        image = nib.Nifti1Image(data, affine)
        cropped_image = crop_img(image, pad=False)
        np.testing.assert_array_equal(cropped_image.affine, affine)
        np.testing.assert_array_equal(cropped_image.get_data(), data)
        new_affine = reorder_affine(affine, shape)
        np.testing.assert_array_equal(np.diagonal(new_affine), np.abs(np.diagonal(new_affine)))
        new_image = resample(image, new_affine, shape)
        np.testing.assert_array_equal(new_image.get_data(), image.get_data())
