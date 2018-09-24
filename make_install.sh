#!/bin/bash

##########################################################
### This script prepares the software for installation ###
##########################################################

# folder for the installation
dirname="Deploy"

echo "The installation folder name is: \"$dirname\""

if [ ! -d $dirname ]
  then
    echo "It currently doesn't exist. Creating it now."
    mkdir ./$dirname
    echo "Folder \"$dirname\" created."
  else
    echo "The folder \"$dirname\" already exists."
fi

# run pyinstaller
pyinstaller.exe --onefile \
                --noconfirm \
                --specpath=$dirname \
                --workpath=${dirname}/build \
                --distpath=${dirname}/dist \
                --add-data='../data/Airfoils;data/Airfoils' \
                --add-data='../data/Menus;data/Menus' \
                --add-data='../icons;icons' \
                src/PyAero.py
