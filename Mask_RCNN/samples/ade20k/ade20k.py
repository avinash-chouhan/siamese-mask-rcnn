import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import scipy.io

import pickle

# Root directory of the project
ROOT_DIR = os.path.abspath("../../")

# Import Mask RCNN
sys.path.append(ROOT_DIR)  # To find local version of the library
from mrcnn.config import Config
from mrcnn import utils

class ADE20KConfig(Config):
    NAME = 'ADE20K'
    IMAGES_PER_GPU = 2
    # GPU_count = 8
    NUM_CLASSES = 1 + 3147

class ADE20KDataset(utils.Dataset):
    def load_ade20k(self, dataset_dir, subset, class_ids=None, class_map=None):
        index = scipy.io.loadmat(dataset_dir + '/index_ade20k.mat')['index'][0][0]

        filenames_relative = [folder[0] + '/' + filename[0] for folder, filename in zip(index[1][0], index[0][0])]
        filenames          = [dataset_dir + '/' + '/'.join(f.split('/')[1:]) for f in filenames_relative]
        objectnames        = [f[0] for f in index[6][0]]
        objectPresence     = index[4].astype(np.int)

        with open(dataset_dir + '/image_sizes.pkl', 'rb') as f:
            image_sizes = pickle.load(f)

        if subset == 'train':
            filter_fn = lambda s: 'training' in s
        elif subset == 'val':
            filter_fn = lambda s: 'validation' in s
        else:
            raise Exception('Unknown subset: {}'.format(subset))

        idx = [i for i, f in enumerate(filenames) if filter_fn(f)]
        filenames      = [filenames[i] for i in idx]
        objectPresence = objectPresence[:, idx]

        if not class_ids:
            # All classes with existing instances
            class_ids = list(np.where(np.sum(objectPresence, 1) > 0)[0])

        if class_ids:
            # Take images of corresponding classes
            image_ids = []
            for class_id in class_ids:
                image_ids.extend(list(np.where(objectPresence[class_id])[0]))
            image_ids = list(set(image_ids))

        # Add classes
        for i in class_ids:
            self.add_class('ade20k', i, objectnames[i])

        # Build annotations (list of classes for all images)
        annotations = []
        for i in image_ids:
            image_classes = np.unique(np.where(objectPresence[:,i] > 0)[0])
            annotations.append({'class_index': image_classes})

        # Add images
        for i in image_ids:
            self.add_image(
                    'ade20k', image_id=i,
                    path=filenames[i],
                    width=image_sizes[filenames_relative[i]][0],
                    height=image_sizes[filenames_relative[i]][1],
                    annotations=annotations[i])

    def load_mask(self, image_id):
        instance_masks = []
        class_ids = []

        # Build mask of shape [height, width, instance_count] and list
        # of class IDs that correspond to each channel of the mask.
        object_mask, instance_mask = loadADE20K(self.image_info[image_id]['path'])

        for instance_id in np.unique(instance_mask):
            instance_id_mask = (instance_mask == instance_id)
            if np.sum(instance_id_mask) < 1:
                continue
            instance_masks.append(instance_id_mask)
            class_ids.append(int(np.median(object_mask[instance_id_mask])))

        if class_ids:
            mask = np.stack(instance_masks, axis=2).astype(np.bool)
            class_ids = np.array(class_ids, dtype=np.int32)
            return mask, class_ids
        else:
            # Call super class to return an empty mask
            return super(CocoDataset, self).load_mask(image_id)

def loadADE20K(filename):
    """
    Python translation of the original MATLAB function.
    So far it only loads the semantic and instance segemntation masks.

    The outputs are
        - Object class masks (n x m)
        - Object instance masks (n x m)
    """
    fileseg = filename.replace('.jpg', '_seg.png')

    seg = plt.imread(fileseg)

    R, G, B = (seg[:,:,0], seg[:,:,1], seg[:,:,2])

    ObjectClassMasks = (R * 255 * 256 / 10 + G * 255).astype(np.int)

    _, Minstances_hat = np.unique(B.ravel(), return_inverse=True)
    ObjectInstanceMasks = np.reshape(Minstances_hat, B.shape).astype(np.int)

    return ObjectClassMasks, ObjectInstanceMasks
