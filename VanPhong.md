# Local Development
## Window

## Linux (Ubuntu 20.04)

- Install python packages:

```bash
sudo apt install -y python3.8-dev python3-venv
```

- Install Posgtgresql:

```bash
sudo apt install postgres-12
```

- Clone repository `van-phong-api`:

```bash
git clone https://github.com/VanThuongSG/vanphong-api.git
```
- Create python virtual environment inside folder `van-phong-api`:

```bash
cd van-phong-api
python3 -m venv py38
# activate virtual environment
source pyvenv/bin/activate
# Install requirement packages
python -m pip install wheel
python -m pip install -r requirements_dev.txt
```

- Create develop database `saleor` and grant pemission for user `saleor` (in production version we should change database name and user name)

```bash
sudo -u postgres psql
create database saleor;
create user saleor with encrypted password 'saleor';
alter user saleor with superuser;
grant all privileges on database saleor to saleor;
```

- Django migrate:

```bash
source py38/bin/activate
# Window: source pyvenv/Scripts/activate
# python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py populatedb --createsuperuser
python manage.py get_graphql_schema > saleor/graphql/schema.graphql
# python manage.py createsuperuser
export ALLOWED_HOSTS=*
export SECRET_KEY=vtsg-dev
python manage.py runserver 0.0.0.0:8000
```

# Mapping Saleor to VanPhong
## Naming conventions
- Using Visual Code or NotePad++ to replace string

| Saleor Dashboard   |      Van Phong Dashboard      |
|----------|--------------|
| `product` |  `room` |
| `products` |    `rooms`   |
| `Product` | `Room` |
| `Products` | `Rooms` |
| `warehouse` | `hotel` |
| `Warehouse` | `Hotel` |
| `/Product` | `/Room` |
| `"product"` | `"room"` |
| `"product` | `"room` |
| \`product | \`room |
| `.product` | `.room` |
| `product.` | `room.` |
| `_product` | `_room` |
| `product_` | `room_` |
| `product"` | `room"` |
| `product =` | `room =` |
| `product,` | `room,` |
| `product=` | `room=` |
| `product[` | `room[` |
| `roomion` | `production` |
| `ROOMION` | `PRODUCTION` |


- Using sample scripts to rename file and folder

```sh
## warehouse -> hotel
# File
for file in $(find van-phong-api -name '*warehouse*.*')
do
    echo mv "$file" "${file/warehouse/hotel}"
    mv $file ${file/product/room}
done
#Folder
for file in $(find van-phong-api -name '*Warehouse*')
do
    echo mv "$file" "${file/Warehouse/Hotel}"
    mv $file ${file/Warehouse/Hotel}
done
```

# Generate Database Modeling
## Install

```bash
sudo apt install graphviz
sudo apt install libgraphviz-dev
source py38/bin/activate
pip install pygraphviz

python -m pip install --global-option=build_ext --global-option="-IC:\cygwin64\usr\include" --global-option="-LC:\cygwin64\lib\graphviz-2.40" pygraphviz

# Same example but with explicit selection of pygraphviz or pydot
python ./manage.py graph_models -a -g -o database_visualization.png
python ./manage.py graph_models --pygraphviz -a -g -o database_visualization.png
# Create a graph for only certain models
python ./manage.py graph_models --pygraphviz -a --arrow-shape normal -g -o database_visualization.png
# Create a graph for only certain models
python ./manage.py graph_models --pygraphviz -a -I Hotel,Room -o hotel_room_subsystem.png
# Create a dot file for only the 'foo' and 'bar' applications of your project
python ./manage.py graph_models Hotel Room > my_project.dot

# Create a graph including models matching a given pattern and excluding some of them
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Payment*,*Transaction* -o database_model/saleor.payment.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Order*,*Fulfillment*,*Invoice*,*Checkout* -o database_model/saleor.order.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Hotel*,*Allocation*,*Stock* -o database_model/saleor.hotel.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Shipping* -o database_model/saleor.shipping.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Webhook* -o database_model/saleor.webhook.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Checkout* -o database_model/saleor.checkout.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Customer*,*User*,*Address*,*Permissions*,*Staff* -o database_model/saleor.account.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Room*,*VariantImage*,*Occurrence*,*AttributeTranslation*,*Attribute*,*Category* -o database_model/saleor.room.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Order*,*Fulfillment*,*Booking*,*Checkout*,*Payment*,*Transaction* -o database_model/saleor.order.png
python manage.py graph_models --pygraphviz -a --arrow-shape normal g -I *Hotel*,*Room*,*Checkout*,*Order*,*Allocation*,*Stock* -o database_model/saleor.hotel.png
```
