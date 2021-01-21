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

find_replace () {
    shopt -s nullglob dotglob

    for pathname in "$1"/*; do
        if [ -d "$pathname" ]; then
            find_replace "$pathname"
        else
            if ! [[ $pathname =~ "__pycache__" ]]; then
                # Rename content
                case "$pathname" in
                    *.py|*.yaml|*.json)
                    printf 'Find and Replace: %s\n' "$pathname"
                    # Mapping Product -> Room
                    sed -i 's/Product/Room/g' $pathname
                    sed -i 's/product/room/g' $pathname
                    sed -i 's/PRODUCT/ROOM/g' $pathname

                    # Mapping Warehouse -> Hotel
                    sed -i 's/Warehouse/Hotel/g' $pathname
                    sed -i 's/warehouse/hotel/g' $pathname
                    sed -i 's/WAREHOUSE/HOTEL/g' $pathname

                    # Change import saleor.xxx to vanphong.xxx
                    sed -i 's/saleor/vanphong/g' $pathname

                    # Convert LF to CRLF
                    sed -i 's/$/\r/g' $pathname
                esac
            fi
        fi
    done
}

lf2crfl () {
    shopt -s nullglob dotglob

    for pathname in "$1"/*; do
        if [ -d "$pathname" ]; then
            lf2crfl "$pathname"
        else
            if ! [[ $pathname =~ "__pycache__" ]]; then
                # Rename content
                case "$pathname" in
                    *.py|*.yaml)
                    printf 'Conver LF to CRLF: %s\n' "$pathname"
                    sed -i 's/$/\r/g' $pathname
                esac
            fi
        fi
    done
}

case "$1" in

    copy_rename)
        copy_rename "saleor"
        ;;
    find_replace)
        find_replace "vanphong"
        ;;
    lf2crfl)
        lf2crfl "vanphong"
        ;;
    clear_pycache)
        find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf
esac

