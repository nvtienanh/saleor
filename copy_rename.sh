#!/bin/bash

copy_rename () {    
    shopt -s nullglob dotglob

    for pathname in "$1"/*; do
        if [ -d "$pathname" ]; then
            copy_rename "$pathname"
        else
            if ! [[ $pathname =~ "__pycache__" ]]; then
                # Rename file
                newpath="$(echo $pathname | sed -e 's/product/room/g')"
                newpath="$(echo $newpath | sed -e 's/warehouse/hotel/g')"
                newpath="$(echo $newpath | sed -e 's/saleor/vanphong/')"
                
                # Move new path
                if ! [ -z "$newpath" ]; then
                    printf 'Copy file: %s\n' "$newpath"
                    mkdir -p `dirname $newpath`
                    cp -r $pathname $newpath
                fi
            fi
        fi
    done
}

copy_rename "saleor"