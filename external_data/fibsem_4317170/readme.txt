###############################################################################

Title:

Convolutional neural networks for segmentation of FIB-SEM nanotomography data from porous polymer films for controlled drug release

Authors:

Fredrik Skärberg, Cecilia Fager, Fransisco Mendoza-Lara, Mats Josefson, Eva Olsson, Niklas Lorén, Magnus Röding

Description:

Dataset and code used in F Skärberg, et al, "Convolutional neural networks for segmentation of FIB-SEM nanotomography data from porous polymer films for controlled drug release", published in Journal of Microscopy. In this work, we develop a segmentation method based on convolutional neural networks (CNNs) for focused ion beam scanning electron microscopy (FIB-SEM) data, acquired from porous polymer films made from ethyl cellulose and hydroxypropyl cellulose (EC/HPC) polymer blends. Herein, all codes in Python/Tensorflow and Matlab necessary to reproduce the results of the paper are supplied, together with the raw data, manual segmentations, trained models, and final segmentation results.

###############################################################################

Begin by unzipping fib_sem_cnn.zip.

-------------------------------------------------------------------------------
Requirements
-------------------------------------------------------------------------------

The Python/Tensorflow code is tested in Python 3.8.5 (Anaconda distribution) and Tensorflow 2.4.0. Additionally, the PIL package for reading .tif images is required (however, it can be replaced by the skimage package instead by slightly modifying the code as described in 'preprocess_data.py').

The Matlab code is tested in Matlab R2020b and requires the Image Processing and Global Optimization toolboxes.

-------------------------------------------------------------------------------
Data preprocessing and preparation
-------------------------------------------------------------------------------

The raw FIB-SEM data for the three data sets (HPC22, HPC30, and HPC45) are available in the folder 'data/raw' as individual 2D slices in .tif format.

First, the data are preprocessed by running 'preprocess_data.py', and the output is saved in 'data/preprocessed' in .npy format (as data volumes, not individual slices).

Second, data regions centered around the manually segmented regions are extracted by running 'extract_data_regions.py', and the output is stored in 'data/regions'. In the same folder, in the files called "ind_squares*.npy", the indices specifying which regions are used for training, validation, and test data are stored. (Note that both the manual segmentation and the data split are taken from previous work as indicated in the paper.)

Third, the data regions and manual segmentations are split into training, validation, and test sets by running 'extract_data_split.py', and the output is stored in 'data/split'.

Fourth, training and validation data for training of the CNNs are extracted (from the training and validation data sets generated in the data split) by running 'extract_data_training.py'. In each case, random voxels (constituting 1 % of the full data) are sampled, with a 50/50 balance between the two classes (pore and solid). 3D neighborhoods of size n_xy * n_xy * n_z are extracted centered around each voxel. Here, the values of n_xy and n_z are the largest ones to be used for any of the architectures (i.e. n_xy = 113 and n_z = 11). The result, neighborhood inputs and binary label outputs, are stored in 'data/datasets'.

-------------------------------------------------------------------------------
Training, hyperparameter optimization, and consolidation of training results
-------------------------------------------------------------------------------

First, the CNN models are defined in 'model_arch.py'. Training and hyperparameter optimization are performed in 'train.py'. Each run is performed for random values of n_xy and n_z as well as for random values of several hyperparameters, as described in the paper. The output is saved in 'training/results_{n_xy}_{n_z}/results_{random_seed}'. The output is the weights of the best model/epoch of the run in model.h5, the hyperparameters and execution time for training in parameters.dat, and the training and validation losses in loss.csv.

Second, the results of the training are consolidated in 'consolidate_training_results.m'. For each neighborhood size, the best model (best run) in terms of validation loss is identified and copied to 'model/model_{n_xy}_{n_z}'. In this repository, the best models found in the paper for each neighborhood size are included.

Third, the performance of all models is assessed in 'predict_all_models.py'. For each neighborhood size, prediction is performed on the training, validation and test data sets (specifically, on the random subsets of voxels and their corresponding neighborhoods as extracted in 'extract_data_training.py'). Binary cross-entropy loss, accuracy, and mIoU are computed for the training, validation and test data sets. Selection of the optimal model (with respect to neighborhood size) can then be performed based on these results, which are output in 'model/model_{n_xy}_{n_z}/results.dat'.

-------------------------------------------------------------------------------
Processing of the full data sets
-------------------------------------------------------------------------------

First, once the final CNN model is selected, the prediction (more precisely, computation of the score) of the full data sets is performed in 'predict_random_slice.py'. As explained in the paper, the code performs the prediction for a random slice in a random dataset, since this facilitates simple parallelization in a cluster environment. By executing this code 600 times, all slices of all datasets will be processed. The output is stored in 'data/score/HPC{dataset}', together with the execution time.

Second, the prediction output is merged in 'merge_prediction_slices.py', which produces binary .bin files intented for Matlab, stored in 'data/score'.

Third, optimization of postprocessing parameters is performed in 'postprocessing_opt.m', where a threshold and the standard deviation of a Gaussian filter are optimized with respect to validation mIoU. In this stage, the random subsets of the training, validation, and test sets extracted in 'extract_data_training.py' are no longer used, but rather the full manually segmented regions. The result of the optimization procedure is saved in 'postprocessing_parameters.mat'.

Fourth, the final postprocessing is applied to the scores in 'postprocessing.m', and segmentations of the full data sets are stored in 'data/seg' in Matlab format and as individual slices in 'data/seg/seg_HPC{dataset}' in .png format. Further, this code computes accuracy, mIoU and porosity values for the training, validation, and test sets, before and after postprocessing.
