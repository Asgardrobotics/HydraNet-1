#!usr/bin/env python

import os
import cv2
import keras_implementation.utilities.logger as logger
from keras_implementation.utilities.image_utils import CLAHE_image_folder, CLAHE_single_image, hist_match_image_folder,\
    hist_match, get_residual
from os.path import isfile, join
import numpy as np
import shutil
import errno
from pathlib import Path


def main(root_dir=(join(Path(__file__).resolve().parents[1], 'data'))):
    """
    Main method ran by the program to create and populate train, val, and test
    datasets.

    :param root_dir: The root directory of the image dataset
    :type root_dir: str
    :return: None
    """

    # Iterate over each volume in the root data directory
    for folder_name in os.listdir(root_dir):
        print(join(root_dir, folder_name))
        if folder_name != 'results':
            create_train_test_val_dirs(join(root_dir, folder_name))
            populate_train_test_val_dirs_nonrandomly(join(root_dir, folder_name), preliminary_clahe=True)

    # Get and save the residuals between ClearImages and CoregisteredBlurryImages
    for folder_name in os.listdir(root_dir):
        if folder_name != 'results':
            create_and_populate_residual_dirs(join(root_dir, folder_name))


def create_train_test_val_dirs(root_dir):
    """
    Creates empty directories that will hold train, validation, and test
    splits of image dataset.

    :param root_dir: The root directory under which the train, val, and test sets will live
    :type root_dir: str

    :return: None
    """
    try:
        # Create training data directories
        os.makedirs(root_dir + '/train')
        os.makedirs(root_dir + '/train/CoregisteredBlurryImages')
        os.makedirs(root_dir + '/train/ClearImages')

        # Create validation data directories
        os.makedirs(root_dir + '/val')
        os.makedirs(root_dir + '/val/CoregisteredBlurryImages')
        os.makedirs(root_dir + '/val/ClearImages')

        # Create testing data directories
        os.makedirs(root_dir + '/test')
        os.makedirs(root_dir + '/test/CoregisteredBlurryImages')
        os.makedirs(root_dir + '/test/ClearImages')
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def create_residual_dirs(root_dir):
    """
    Creates empty directories that will hold residual images for train, validation, and test
    splits of image dataset.

    :param root_dir: The root directory under which the train/Residuals, val/Residuals, and test/Residuals
                        directories will live
    :type root_dir: str

    :return: None
    """
    try:
        # Create residual directories
        os.makedirs(root_dir + '/train/Residuals')
        os.makedirs(root_dir + '/val/Residuals')
        os.makedirs(root_dir + '/test/Residuals')

    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def create_and_populate_residual_dirs(root_dir):
    """
    Creates empty directories that will hold residual images for train, validation, and test
    splits of image dataset.

    :param root_dir: The root directory under which the train/Residuals, val/Residuals, and test/Residuals
                        directories will live
    :type root_dir: str

    :return: None
    """
    try:
        # Create residual directories
        os.makedirs(root_dir + '/train/Residuals')
        os.makedirs(root_dir + '/val/Residuals')
        os.makedirs(root_dir + '/test/Residuals')

    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    # Now, populate the residual dirs
    populate_residual_dirs(join(root_dir, 'train'))
    populate_residual_dirs(join(root_dir, 'val'))
    populate_residual_dirs(join(root_dir, 'test'))


def populate_residual_dirs(root_dir):
    """
    Populates the Residuals directories with the difference (residuals) between clear and blurry images

    :param root_dir: The parent directory of the Residuals directory, where the ClearImages and
                        CoregisteredBlurryImages directories also live

    :return: None
    """

    # Get the full path of the ClearImages and CoregisteredBlurryImages directories
    clear_image_dir = join(root_dir, 'ClearImages')
    blurry_image_dir = join(root_dir, 'CoregisteredBlurryImages')
    residual_dir = join(root_dir, 'Residuals')

    # Iterate over the entire list of images (doesn't matter if it's clear_image_dir or blurry_image_dir)
    for file_name in os.listdir(clear_image_dir):
        if file_name.endswith('.jpg') or file_name.endswith('.png'):

            # Read the clear and blurry images as grayscale images in the form of numpy arrays
            clear_image = cv2.imread(join(clear_image_dir, file_name), 0)
            blurry_image = cv2.imread(join(blurry_image_dir, file_name), 0)

            # Calculate the residual of the two images
            residual_image = get_residual(clear_image=clear_image, blurry_image=blurry_image)

            # Clip the residual image so that negative pixel values are clipped to 0 (black), so
            # that when we convert to [0, 255] range, negative pixels stay black
            residual_image_clipped = np.clip(residual_image, a_min=0, a_max=1)

            # Scaled the image to the range [0, 255]
            scaled_residual_image = (residual_image_clipped * 255).astype(np.uint8)

            ''' Just logging 
            # Show the clear image, blurry image, and resulting residual image
            logger.show_images([("clear_image", clear_image),
                                ("blurry_image", blurry_image),
                                ("residual_image [-1, 1]", residual_image),
                                ("residual_image_clipped [0, 1]", residual_image_clipped),
                                ("scaled_residual_image [0, 255]", scaled_residual_image)])
            '''

            # Save the image
            cv2.imwrite(filename=join(residual_dir, file_name), img=scaled_residual_image)

            print(f'Saved a residual image. The filename is {join(residual_dir, file_name)}')


def populate_train_test_val_dirs_nonrandomly(root_dir, val_ratio=0.15, test_ratio=0.05, preliminary_clahe=True):
    """
    Populates the train, val, and test folders with the images located in root_dir,
    according to val_ratio  and test_ratio

    :param root_dir: The root directory of the image dataset
    :type root_dir: str
    :param val_ratio: The desired ratio of val images to total images
    :type val_ratio: float
    :param test_ratio: The desired ratio of test images to total images
    :type test_ratio: float
    :param preliminary_clahe: True if we want to perform CLAHE before applying further
                                histogram equalization
    :type preliminary_clahe: bool

    :return: None
    """

    ''' Creating partitions of the data after shuffling '''
    # Folder to copy images from
    src = join(root_dir, 'CoregisteredBlurryImages')

    all_file_names = [f for f in os.listdir(src) if isfile(join(src, f))]

    # Select the number of images to skip between validation images
    val_skip_number = len(all_file_names) / (val_ratio * len(all_file_names))

    # Select the number of images to skip between test images
    test_skip_number = len(all_file_names) / (test_ratio * len(all_file_names))

    # Get the list of validation file names, test file names, and train file names
    val_file_names = all_file_names[::int(val_skip_number)]
    test_file_names = [filename for filename in all_file_names[::int(test_skip_number + 1)]
                       if filename not in val_file_names]
    train_file_names = [filename for filename in all_file_names
                        if filename not in val_file_names and filename not in test_file_names]

    # Print the file distribution among the folders
    logger.print_file_distribution(len(all_file_names), len(train_file_names), len(val_file_names), len(test_file_names))

    # Copy-Pasting images into train dataset, then normalizing them using CLAHE
    for name in train_file_names:
        shutil.copy(join(root_dir, 'CoregisteredBlurryImages', name), root_dir + '/train/CoregisteredBlurryImages')
        shutil.copy(join(root_dir, 'ClearImages', name), root_dir + '/train/ClearImages')

    # Copy-Pasting images into val dataset, then normalizing them using CLAHE
    for name in val_file_names:
        shutil.copy(join(root_dir, 'CoregisteredBlurryImages', name), root_dir + '/val/CoregisteredBlurryImages')
        shutil.copy(join(root_dir, 'ClearImages', name), root_dir + '/val/ClearImages')

    # Copy-Pasting images into test dataset, then normalizing them using CLAHE
    for name in test_file_names:
        shutil.copy(join(root_dir, 'CoregisteredBlurryImages', name), root_dir + '/test/CoregisteredBlurryImages')
        shutil.copy(join(root_dir, 'ClearImages', name), root_dir + '/test/ClearImages')

    ''' Augment the images in each new folder '''
    # If we want to use preliminary adaptive equalization...
    if preliminary_clahe:
        pass
        # ... then first, apply Contrast Limited Adaptive Histogram Equalization to ALL images in all folders
        # CLAHE_image_folder(root_dir + '/train/CoregisteredBlurryImages')
        CLAHE_image_folder(root_dir + '/train/ClearImages')
        # CLAHE_image_folder(root_dir + '/val/CoregisteredBlurryImages')
        CLAHE_image_folder(root_dir + '/val/ClearImages')
        # CLAHE_image_folder(root_dir + '/test/CoregisteredBlurryImages')
        CLAHE_image_folder(root_dir + '/test/ClearImages')


    # Then, apply histogram equalization to make the blurry images' histogram match that of the clear images
    hist_match_image_folder(root_dir=join(root_dir, 'train'),
                            clear_dir_name='ClearImages',
                            blurry_dir_name='CoregisteredBlurryImages',
                            match_to_clear=True)
    hist_match_image_folder(root_dir=join(root_dir, 'val'),
                            clear_dir_name='ClearImages',
                            blurry_dir_name='CoregisteredBlurryImages',
                            match_to_clear=True)
    hist_match_image_folder(root_dir=join(root_dir, 'test'),
                            clear_dir_name='ClearImages',
                            blurry_dir_name='CoregisteredBlurryImages',
                            match_to_clear=True)


def populate_train_test_val_dirs_randomly(root_dir=(os.getcwd()), val_ratio=0.15, test_ratio=0.05):
    """
    Populates the train, val, and test folders with the images located in root_dir,
    according to val_ratio  and test_ratio

    :param root_dir: The root directory of the image dataset
    :type root_dir: str
    :param val_ratio: The desired ratio of val images to total images
    :type val_ratio: float
    :param test_ratio: The desired ratio of test images to total images
    :type test_ratio: float
    :return: None
    """
    # Creating partitions of the data after shuffling
    # Folder to copy images from
    src = root_dir  # The folder to copy images from

    all_file_names = [f for f in os.listdir(src) if isfile(join(src, f))]

    np.random.shuffle(all_file_names)

    train_file_names, val_file_names, test_file_names = np.split(np.array(all_file_names),
                                                                 [int(len(all_file_names) * (
                                                                         1 - val_ratio + test_ratio)),
                                                                  int(len(all_file_names) * (1 - test_ratio))])
    # Print the file distribution amongst the folders
    logger.print_file_distribution(len(all_file_names), len(train_file_names), len(val_file_names), len(test_file_names))

    print(train_file_names)

    # Copy-Pasting Images
    for name in train_file_names:
        shutil.copy(join(root_dir, 'CoregisteredBlurryImages', name), root_dir + '/train/CoregisteredBlurryImages')
        shutil.copy(join(root_dir, 'ClearImages', name), root_dir + '/train/ClearImages')
    for name in val_file_names:
        shutil.copy(join(root_dir, 'CoregisteredBlurryImages', name), root_dir + '/val/CoregisteredBlurryImages')
        shutil.copy(join(root_dir, 'ClearImages', name), root_dir + '/val/ClearImages')
    for name in test_file_names:
        shutil.copy(join(root_dir, 'CoregisteredBlurryImages', name), root_dir + '/test/CoregisteredBlurryImages')
        shutil.copy(join(root_dir, 'ClearImages', name), root_dir + '/test/ClearImages')


if __name__ == "__main__":

    # Get the root directory by going "up" two directories
    rootdir = Path(__file__).resolve().parents[1]

    # Pass that root directory to the main function
    main(root_dir=join(rootdir, 'data'))
