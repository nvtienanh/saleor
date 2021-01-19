#!/bin/bash
find_replace () {
    shopt -s nullglob dotglob

    for pathname in "$1"/*; do
        if [ -d "$pathname" ]; then
            find_replace "$pathname"
        else
            if ! [[ $pathname =~ "__pycache__" ]]; then
                # Rename content
                case "$newpath" in
                    *.py|*.yaml)
                    sed -i 's/Product/Room/g' $newpath
                    sed -i 's/Product/Room/g' $newpath
                esac
            fi
        fi
    done
}

find_replace "vanphong"
