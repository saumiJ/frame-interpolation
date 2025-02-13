# Copyright 2023 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
r"""Beam pipeline that generates CFD triplet TFRecords.

Input to the script is the root-folder that contains the unzipped folders
of input pairs (other-data) and golden frames (other-gt-interp).

Output TFRecord is a tf.train.Example proto of each image triplet.

Usage example:
  python3 -m frame_interpolation.datasets.create_cfd_tfrecord \
    --input_dir=<root folder of cfd-other> \
    --output_tfrecord_filepath=<output tfrecord filepath>
"""

import os

from . import util
from absl import app
from absl import flags
from absl import logging
import apache_beam as beam
import tensorflow as tf

_INPUT_DIR = flags.DEFINE_string(
    'input_dir',
    default='/root/path/to/cfd-data',
    help='Path to the root directory of the CFD-dataset.'
    'Folders in said directory:\n'
    'other-data/\n'
    '|  001-re-60-wake-init\n'
    '|  |  frame10.png\n'
    '|  |  frame11.png\n'
    '|  002-re-60-osc\n'
    '|  |  frame10.png\n'
    '|  |  frame11.png\n'
    '|  ...\n'
    'other-gt-interp/\n'
    '|  001-re-60-wake-init\n'
    '|  |  frame10i11.png\n'
    '|  002-re-60-osc\n'
    '|  |  frame10i11.png\n'
    '|  ...\n')

_INPUT_PAIRS_FOLDERNAME = flags.DEFINE_string(
    'input_pairs_foldername',
    default='other-data',
    help='Foldername containing the folders of the input frame pairs.')

_GOLDEN_FOLDERNAME = flags.DEFINE_string(
    'golden_foldername',
    default='other-gt-interp',
    help='Foldername containing the folders of the golden frame.')

_OUTPUT_TFRECORD_FILEPATH = flags.DEFINE_string(
    'output_tfrecord_filepath',
    default=None,
    required=True,
    help='Filepath to the output TFRecord file.')

_NUM_SHARDS = flags.DEFINE_integer('num_shards',
    default=3,
    help='Number of shards used for the output.')

# Image key -> basename for frame interpolator: start / middle / end frames.
_INTERPOLATOR_IMAGES_MAP = {
    'frame_0': 'frame10.png',
    'frame_1': 'frame10i11.png',
    'frame_2': 'frame11.png',
}


def main(unused_argv):
  """Creates and runs a Beam pipeline to write frame triplets as a TFRecord."""
  # Collect the list of folder paths containing the input and golden frames.
  pairs_list = tf.io.gfile.listdir(
      os.path.join(_INPUT_DIR.value, _INPUT_PAIRS_FOLDERNAME.value))

  folder_names = [
      _INPUT_PAIRS_FOLDERNAME.value, _GOLDEN_FOLDERNAME.value,
      _INPUT_PAIRS_FOLDERNAME.value
  ]
  triplet_dicts = []
  for pair in pairs_list:
    triplet_dict = {
        image_key: os.path.join(_INPUT_DIR.value, folder, pair, image_basename)
        for folder, (image_key, image_basename
                    ) in zip(folder_names, _INTERPOLATOR_IMAGES_MAP.items())
    }
    triplet_dicts.append(triplet_dict)

  p = beam.Pipeline('DirectRunner')
  (p | 'ReadInputTripletDicts' >> beam.Create(triplet_dicts)  # pylint: disable=expression-not-assigned
   | 'GenerateSingleExample' >> beam.ParDo(
       util.ExampleGenerator(_INTERPOLATOR_IMAGES_MAP))
   | 'WriteToTFRecord' >> beam.io.tfrecordio.WriteToTFRecord(
       file_path_prefix=_OUTPUT_TFRECORD_FILEPATH.value,
       num_shards=_NUM_SHARDS.value,
       coder=beam.coders.BytesCoder()))
  result = p.run()
  result.wait_until_finish()

  logging.info('Succeeded in creating the output TFRecord file: \'%s@%s\'.',
    _OUTPUT_TFRECORD_FILEPATH.value, str(_NUM_SHARDS.value))

if __name__ == '__main__':
  app.run(main)
