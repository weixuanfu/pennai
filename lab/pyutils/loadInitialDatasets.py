'''
Script to validate and register with the PennAI server all the .csv or .tsv files in a directory as datasets
'''

import argparse
import sys
import simplejson
from sklearn.utils import check_X_y
import os
import os.path
import pandas as pd
import numpy as np
import logging
import requests
import time


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

DEFAULT_TARGET_COLUMN = "class"


def registerDatafiles(directory, apiPath):
	'''
	Register all the datafiles in directory with the lab server
	'''

	logger.info("============")
	logger.info("Register datafiles in directory '" + directory + "'")

	# infinite recursion can occur if symlink points to the parent directory, see <https://docs.python.org/3/library/os.html#os.walk>
	for root, dirs, files in os.walk(directory, topdown=True, onerror=None, followlinks=True):
		for file in files:
			extension = os.path.splitext(file)[1]

			if (extension in ['.csv', '.tsv']):
				foundMetadataFile, target_column, categorical_features, ordinal_features = getMetadataForDatafile(root, file)
				registerDatafile(root, file, target_column, categorical_features, ordinal_features, apiPath)		


def getMetadataForDatafile(root, file):
	'''
	Check to see if there is a metadata .json file for the data file, if so attempt to use it to get 
	dataset metadata.

	Currently only looks for 'target_column', in the future may also include other data such as 
	which columns should represent catagorial features.

	For a dataset named "dataset.csv", the analogous metadata file would be "dataset_metadata.json"

	@return tuple
		boolean - was metadata extracted
		string 	- target_column
	'''
	metafile = os.path.splitext(file)[0] + "_metadata.json"
	filepath = os.path.join(root, metafile)

	target_column = DEFAULT_TARGET_COLUMN
	categorical_features = []
	ordinal_features = {}

	# Try to open and parse the file
	try:
		with open(filepath) as f:
			data = simplejson.load(f)
	except FileNotFoundError:
		logger.info("File " + metafile + " does not exist, using default metadata.")
		return False, target_column, categorical_features, ordinal_features
	except Exception as e:
		logger.error("Unable to parse file " + filepath + ": " + str(e))
		return False, target_column, categorical_features, ordinal_features

	# extract matadata from the file
	if ('target_column' in data.keys()):
		target_column = data['target_column']
	else:
		logger.warning("Could not get 'target_column' from file " + filepath)

	if ('categorical_features' in data.keys()): categorical_features = data['categorical_features']
	else: logger.warning("Could not get 'categorical_features' from file " + filepath)

	if ('ordinal_features' in data.keys()): ordinal_features = data['ordinal_features']
	else: logger.warning("Could not get 'ordinal_features' from file " + filepath)

	return True, target_column, categorical_features, ordinal_features



def registerDatafile(root, file, target_column, categorical_features, ordinal_features, apiPath):
	'''
	Register a datafile with the main PennAI server
	'''
	filepath = os.path.join(root, file)
	path = apiPath + "/api/v1/datasets"

	logger.debug("registering file:" + root + " " + file)
	logger.debug("api path: " + path)
	logger.debug("target_column: " + str(target_column) + " categorical_features: " + str(categorical_features) + " ordinal_features: " + str(ordinal_features))

	payload = {'_metadata' : simplejson.dumps({
		'name': os.path.splitext(file)[0],
		'username': 'testuser',
		'dependent_col' : target_column,
		'categorical_features' : categorical_features,
		'ordinal_features' : ordinal_features
		})
	}

	logger.debug("payload: " + str(payload))

	files = {'_files': open(filepath, 'rb')}

	res = None
	try:
		res = requests.request('PUT', path, files=files, data=payload)
	except:
		logger.error("Unexpected error in registerDatafile for path 'PUT:" + str(path) + "': " + str(sys.exc_info()[0]))
		raise
	
	if res.status_code != requests.codes.ok:
		msg = "Error registering datafile, request PUT status_code not ok, path: '" + str(path) + "'' status code: '" + str(res.status_code) + "'' response text: " + str(res.text)
		logger.error(msg)
	else:
		logger.info("Datafile '" + filepath + "' registered: " + str(res.status_code) + " : " + str(res.text))



def main():
	'''
	Attempt to load the inital datasets using the user directory and lab host defined in environmental variables

	Also add an additional file log handler to '../target/log/loadInitialDatasets.log'
	'''
	meta_features_all = []
	parser = argparse.ArgumentParser(description="Reads or creates 'DATASET_metadata.json' file given a dataset", add_help=False)
	#parser.add_argument('DIRECTORY', type=str, help='Direcory to get get datafiles from')    

	args = parser.parse_args()

	# set up the file logger
	logpath = os.path.join(os.environ['PROJECT_ROOT'], "target/logs")
	if not os.path.exists(logpath):
		os.makedirs(logpath)

	formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
	fhandler = logging.FileHandler(os.path.join(logpath, 'loadInitialDatasets.log'))
	fhandler.setFormatter(formatter)
	logger.addHandler(fhandler)

	print("logpath: " + logpath)
	print(os.path.join(logpath, 'loadInitialDatasets.log'))

	apiPath = 'http://' + os.environ['LAB_HOST'] + ':' + os.environ['LAB_PORT']
	directory = os.environ['STARTUP_DATASET_PATH']

	registerDatafiles(directory, apiPath)   

if __name__ == '__main__':
	main()