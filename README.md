# SPATRAC

# Inventory Management System

This is an Inventory Management System developed using Python, PySimpleGUI, and Pandas. The system allows for tracking the delivery and processing of products, including generating barcodes and viewing detailed inventory information.

## Features

- **Product Delivery**: Register the delivery of products, generate batch/lot numbers, and track initial quality checks.
- **Product Processing**: Process delivered products, update their status, and move them to the appropriate department and sub-department.
- **Barcode Generation**: Automatically generate and display barcodes for each product.
- **Inventory Management**: View a table of all products in the inventory with detailed information, including product codes, descriptions, and status.

## Requirements

 - Pbarcode==1.0.4
 - Levenshtein==0.25.1
 - numpy==2.1.0
 - pandas==2.2.2
 - pillow==10.4.0
 - pyasn1==0.6.0
 - PySimpleGUI==5.0.6
 - python-barcode==0.15.1
 - python-dateutil==2.9.0.post0
 - python-Levenshtein==0.25.1
 - pytz==2024.1
 - rapidfuzz==3.9.6
 - rsa==4.9
 - setuptools==73.0.1
 - six==1.16.0
 - tzdata==2024.1
 

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/Manakin-Wraith/SPATRAC.git
    ```
2. Navigate to the project directory:
    ```bash
    cd SPATRAC
    ```
3. Install the required Python packages:
    ```bash
    pip install requirements.txt
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

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction for personal, educational, or non-commercial use, including without limitation the rights to use, copy, modify, merge, publish, and distribute copies of the Software, subject to the following conditions:

1. The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

2. Commercial use of the Software, including but not limited to using the Software as part of a business offering, for generating revenue, or within a commercial product, requires a separate commercial license agreement with [Gerhard Mostert/Celebration House Entertainment CC.].

3. Any distribution or modification of the Software for commercial purposes must be done under a commercial license obtained from [Gerhard Mostert/Celebration House Entertainment CC.]. For inquiries regarding commercial licensing, please contact [Your Contact Information].

4. Any use of trademarks, logos, or branding associated with the Software requires explicit permission from [Gerhard Mostert/Celebration House Entertainment CC.].

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Additional Terms:
- This license does not grant any rights to use the Software for commercial purposes without a separate commercial license.
- [Add any additional proprietary claims, trademarks, or specific terms here.]

For commercial licensing inquiries, contact: [Your Contact Information]


## Acknowledgments

- This project was developed using [PySimpleGUI](https://pysimplegui.readthedocs.io/), [Pandas](https://pandas.pydata.org/), and [python-barcode](https://github.com/WhyNotHugo/python-barcode).


