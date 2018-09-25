#!/bin/bash

##########################################################
### This script prepares the software for installation ###
##########################################################

# folder for the installation
dirname="Deploy"

# check for arguments
for i;do
  # when using "clean" as argument, then delete installation folder if it exists
  if [[ $i = clean && -d $dirname ]]; then
    rm -rf ./$dirname
    echo "Folder \"$dirname\" deleted."
  fi
done

echo " "
echo "##########################################################"
echo "############### Preparing to deploy ######################"
echo "##########################################################"
echo " "

echo "The installation folder name is: \"$dirname\""

if [ ! -d $dirname ]; then
  echo "It currently doesn't exist. Creating it now."
  mkdir ./$dirname
  echo "Folder \"$dirname\" created."
else
    echo "The folder \"$dirname\" already exists."
fi

echo " "
echo "##########################################################"
echo "############## Running PyInstaller  ######################"
echo "##########################################################"
echo " "

# run pyinstaller
# use --onefile to make one file only
# use --onedir to have everything in one folder
pyinstaller.exe --onefile \
                --noconfirm \
                --windowed \
                --specpath=$dirname \
                --workpath=${dirname}/build \
                --distpath=${dirname}/dist \
                src/PyAero.py
