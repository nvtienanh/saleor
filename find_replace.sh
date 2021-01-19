#!/bin/bash
find_replace () {
    shopt -s nullglob dotglob

    for pathname in "$1"/*; do
        if [ -d "$pathname" ]; then
            find_replace "$pathname"
        else
            if ! [[ $pathname =~ "__pycache__" ]]; then
                # Rename content
                case "$pathname" in
                    *.py|*.yaml)
                    # Mapping Product -> Room
                    sed -i 's/Product/Room/g' $pathname
                    sed -i 's/product/room/g' $pathname
                    sed -i 's/PRODUCT/ROOM/g' $pathname

                    # Mapping Warehouse -> Hotel
                    sed -i 's/Warehouse/Hotel/g' $pathname
                    sed -i 's/warehouse/hotel/g' $pathname
                    sed -i 's/WAREHOUSE/HOTEL/g' $pathname
                esac
            fi
        fi
    done
}

find_replace "vanphong"
