## SPATRAC Inventory Management System

SPATRAC is a comprehensive Inventory Management System developed using Python, PySimpleGUI, and Pandas. The system allows for tracking the delivery and processing of products, including generating barcodes, viewing detailed inventory information, and maintaining user authentication.

## Features

- **User Authentication**: Secure login system to control access to the application.
- **Product Delivery**: Register the delivery of products, generate batch/lot numbers, and track initial quality checks.
- **Product Processing**: Process delivered products, update their status, and move them to the appropriate department and sub-department.
- **Barcode Generation**: Automatically generate and display barcodes for each product.
- **Inventory Management**: View a table of all products in the inventory with detailed information, including product codes, descriptions, and status.
- **Temperature Logging**: Record and track temperature logs for products.
- **Traceability Reports**: Generate and export detailed traceability reports in PDF and CSV formats.
- **Search Functionality**: Easily search for products using various criteria.

## Requirements

See `requirements.txt` for a full list of dependencies.

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
    pip install -r requirements.txt
    ```

## Usage

1. Ensure you have a CSV file with the product data. The file should include columns such as `Product Code`, `Supplier Product Code`, `Product Description`, `Supplier Name`, `Department`, and `Sub-Department`.
2. Run the application:
    ```bash
    python main.py
    ```
3. Log in using the provided credentials.
4. In the GUI, you can:
    - Search for products by description, product code, or supplier product code.
    - Receive a product by entering the required information and clicking "Receive Product".
    - View and manage the inventory, including processing products and generating barcodes.
    - Generate traceability reports and export them as PDF or CSV.

## Code Overview

- **main.py**: Contains the main application logic, GUI creation, and inventory management functions.
- **auth_system.py**: Implements the user authentication system.

Key functions include:
- `create_gui(df)`: Creates and manages the main GUI for the application.
- `deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date, auth_system)`: Registers the delivery of a product.
- `process_product(product, auth_system)`: Updates the product's status to "Processed" and logs its movement.
- `view_detailed_inventory(inventory, auth_system)`: Displays detailed information about the inventory in a separate window.
- `show_traceability_report(items)`: Generates and displays traceability reports.

## Support

For support, feature requests, or bug reports, please contact:
[Your Support Contact Information]

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


