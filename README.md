# SPATRAC

# Inventory Management System

This is an Inventory Management System developed using Python, PySimpleGUI, and Pandas. The system allows for tracking the delivery and processing of products, including generating barcodes and viewing detailed inventory information.

## Features

- **Product Delivery**: Register the delivery of products, generate batch/lot numbers, and track initial quality checks.
- **Product Processing**: Process delivered products, update their status, and move them to the appropriate department and sub-department.
- **Barcode Generation**: Automatically generate and display barcodes for each product.
- **Inventory Management**: View a table of all products in the inventory with detailed information, including product codes, descriptions, and status.

## Requirements

- Python 3.x
- Pandas
- PySimpleGUI
- Pillow
- python-barcode

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/Manakin-Wraith/SPATRAC.git
    ```
2. Navigate to the project directory:
    ```bash
    cd inventory-management-system
    ```
3. Install the required Python packages:
    ```bash
    pip install pandas pysimplegui pillow python-barcode
    ```

## Usage

1. Ensure you have a CSV file with the product data. The file should include columns such as `Product Code`, `Supplier Product Code`, `Product Description`, `Supplier Name`, `Department`, and `Sub-Department`.
2. Run the application:
    ```bash
    python main.py
    ```
3. In the GUI, you can:
    - Enter a product code, supplier product code, or product description to retrieve and display product information.
    - Deliver a product by entering the quantity and clicking "Deliver". This will register the delivery and generate a batch/lot number.
    - Process a product by selecting it from the inventory table and clicking "Process". This updates the product's status and moves it to the appropriate department.
    - View detailed inventory information by clicking "View Inventory".

## Code Overview

- **load_data(file_path)**: Loads the product data from a CSV file.
- **deliver_product(df, product_code, quantity)**: Registers the delivery of a product and generates a batch/lot number.
- **process_product(product)**: Updates the product's status to "Processed" and logs its movement.
- **generate_barcode(data)**: Generates a barcode for the provided data using the Code 128 standard.
- **create_gui(df)**: Creates and manages the main GUI for the application.
- **view_detailed_inventory(inventory)**: Displays detailed information about the inventory in a separate window.

## Sub-Department Mapping

The application includes a predefined mapping of sub-department codes to names, which is used to categorize products during processing.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

MIT License

© [Gerhard Mostert/Celebration House Entertainment CC.] [2024]. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Additional Terms:
[Describe any additional proprietary claims, trademarks, or specific terms here.]


## Acknowledgments

- This project was developed using [PySimpleGUI](https://pysimplegui.readthedocs.io/), [Pandas](https://pandas.pydata.org/), and [python-barcode](https://github.com/WhyNotHugo/python-barcode).


