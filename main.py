import pandas as pd
import PySimpleGUI as sg
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import io
from PIL import Image

# Load the data
def load_data(file_path):
    df = pd.read_csv(file_path, encoding='iso-8859-1', sep=';')
    df.columns = df.iloc[0]
    df = df.iloc[1:]
    return df

# Sub-department mapping
SUB_DEPT_MAPPING = {
    '201': ('CALLC', 'BUTCHERY'),
    '202': ('CBEEF', 'BEEF'),
    '203': ('CCHIC', 'BUTCHERY CHICKENS'),
    '204': ('CLAMB', 'LAMB'),
    '205': ('CMUTT', 'MUTTON'),
    '206': ('COFFL', 'ALL OFFAL'),
    '207': ('CPORK', 'PORK'),
    '208': ('CTURK', 'BUTCHERY TURKEY'),
    '209': ('CVEAL', 'VEAL'),
    '210': ('CBING', 'INGREDIENTS'),
    '211': ('CALPAC', 'BUTCHERY PACKAGING')
}

# Simulate product delivery
def deliver_product(df, product_code, quantity):
    product = df[df['Product Code'] == product_code].iloc[0]
    batch_lot = f'LOT-{datetime.now().strftime("%Y%m%d")}-{product_code}'
    return {
        'Product Code': product_code,
        'Product Description': product['Product Description'],
        'Supplier': product['Supplier Name'],
        'Batch/Lot': batch_lot,
        'Department': product['Department'],
        'Sub-Department': SUB_DEPT_MAPPING.get(str(product['Sub-Department']), ('Unknown', 'Unknown'))[1],
        'Quantity': quantity,
        'Delivery Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Status': 'Delivered',
        'Processing Date': '',
        'Current Location': 'Receiving',
        'Handling History': f'Received at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        'Quality Checks': 'Initial check: Passed',
        'Temperature Log': []
    }

# Simulate product processing
def process_product(product):
    product['Status'] = 'Processed'
    product['Processing Date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Current Location'] = f"{product['Department']} - {product['Sub-Department']}"
    product['Handling History'] += f"\nMoved to {product['Current Location']} at {product['Processing Date']}"
    product['Quality Checks'] += f"\nPre-processing check: Passed"
    return product

# Generate barcode
def generate_barcode(data):
    code128 = barcode.get_barcode_class('code128')
    rv = io.BytesIO()
    code128(data, writer=ImageWriter()).write(rv)
    image = Image.open(rv)
    image.thumbnail((300, 300))
    bio = io.BytesIO()
    image.save(bio, format="PNG")
    return bio.getvalue()

# View detailed inventory
def view_detailed_inventory(inventory):
    headings = ['Product Code', 'Description', 'Supplier', 'Batch/Lot', 'Department', 'Sub-Department', 'Quantity', 'Delivery Date', 'Status', 'Processing Date', 'Current Location']
    
    table_data = []
    for item in inventory:
        row = [
            item.get('Product Code', ''),
            item.get('Product Description', ''),
            item.get('Supplier', ''),
            item.get('Batch/Lot', ''),
            item.get('Department', ''),
            item.get('Sub-Department', ''),
            item.get('Quantity', ''),
            item.get('Delivery Date', ''),
            item.get('Status', ''),
            item.get('Processing Date', ''),
            item.get('Current Location', '')
        ]
        table_data.append(row)
    
    layout = [
        [sg.Text('Detailed Inventory', font=('Helvetica', 20))],
        [sg.Table(values=table_data,
                  headings=headings,
                  display_row_numbers=False,
                  auto_size_columns=False,
                  col_widths=[12, 30, 20, 15, 15, 15, 10, 20, 10, 20, 15],
                  num_rows=min(25, len(inventory)),
                  key='-INV_TABLE-',
                  enable_events=True)],
        [sg.Button('View Traceability Report'), sg.Button('Record Temperature'), sg.Button('Generate Barcode'), sg.Button('Close')]
    ]

    window = sg.Window('Detailed Inventory', layout, resizable=True, size=(1300, 600))

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == 'Close':
            break
        elif event == 'View Traceability Report':
            if values['-INV_TABLE-']:
                show_traceability_report(inventory[values['-INV_TABLE-'][0]])
            else:
                sg.popup_error('Please select a product')
        elif event == 'Record Temperature':
            if values['-INV_TABLE-']:
                record_temperature(inventory[values['-INV_TABLE-'][0]])
            else:
                sg.popup_error('Please select a product')
        elif event == 'Generate Barcode':
            if values['-INV_TABLE-']:
                generate_and_show_barcode(inventory[values['-INV_TABLE-'][0]])
            else:
                sg.popup_error('Please select a product')

    window.close()

# Show traceability report
def show_traceability_report(item):
    report = f"""
    Traceability Report for Product: {item['Product Description']}
    -----------------------------------------------------
    Product Code: {item['Product Code']}
    Supplier: {item['Supplier']}
    Batch/Lot Number: {item['Batch/Lot']}
    
    Delivery Information:
    - Delivery Date: {item['Delivery Date']}
    - Quantity Received: {item['Quantity']}
    
    Processing Information:
    - Department: {item['Department']}
    - Sub-Department: {item['Sub-Department']}
    - Processing Date: {item['Processing Date']}
    - Current Status: {item['Status']}
    - Current Location: {item['Current Location']}
    
    Handling History:
    {item['Handling History']}
    
    Quality Checks:
    {item['Quality Checks']}
    
    Temperature Log:
    {'\n'.join(item['Temperature Log']) if item['Temperature Log'] else 'No temperature logs recorded'}
    """
    sg.popup_scrolled(report, title=f'Traceability Report - {item["Product Code"]}')

# Record temperature
def record_temperature(item):
    layout = [
        [sg.Text('Record Temperature')],
        [sg.Input(key='-TEMP-')],
        [sg.Button('Submit'), sg.Button('Cancel')]
    ]
    window = sg.Window('Record Temperature', layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        if event == 'Submit':
            try:
                temp = float(values['-TEMP-'])
                item['Temperature Log'].append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {temp}°C")
                sg.popup('Temperature recorded successfully')
                break
            except ValueError:
                sg.popup_error('Please enter a valid temperature')
    window.close()

# Generate and show barcode
def generate_and_show_barcode(item):
    barcode_data = generate_barcode(item['Batch/Lot'])
    layout = [
        [sg.Text(f"Barcode for {item['Product Description']}")],
        [sg.Image(data=barcode_data)],
        [sg.Button('Close')]
    ]
    window = sg.Window('Barcode', layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
    window.close()

# Create the GUI
def create_gui(df):
    sg.theme('LightBlue2')

    # Define column layouts
    input_column = [
        [sg.Text('Product Code', size=(15, 1)), sg.Input(key='-PRODUCT-', size=(20, 1)), sg.Combo(df['Product Description'].tolist(), key='-PRODUCT_DESC-', size=(20, 1))],
        [sg.Text('Quantity', size=(15, 1)), sg.Input(key='-QUANTITY-', size=(20, 1))],
        [sg.Button('Deliver', size=(15, 1)), sg.Button('Process', size=(15, 1))],
        [sg.Button('View Inventory', size=(15, 1))],
        [sg.Text('_'*40)],
        [sg.Text('Product Information', font=('Helvetica', 16))],
        [sg.Text('', size=(30, 1), key='-PROD_INFO-')],
        [sg.Text('', size=(30, 1), key='-SUPP_INFO-')],
        [sg.Text('', size=(30, 1), key='-DEPT_INFO-')],
    ]

    table_column = [
        [sg.Table(values=[],
                  headings=['Product Code', 'Description', 'Batch/Lot', 'Quantity', 'Status'],
                  display_row_numbers=False,
                  auto_size_columns=False,
                  col_widths=[15, 40, 20, 10, 10],
                  num_rows=10,
                  key='-TABLE-')]
    ]

    layout = [
        [sg.Column(input_column), sg.VSeperator(), sg.Column(table_column)]
    ]

    window = sg.Window('Inventory Management System', layout, finalize=True)

    inventory = []

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break

        # Product selection from description
        if values['-PRODUCT_DESC-']:
            selected_product = df[df['Product Description'] == values['-PRODUCT_DESC-']].iloc[0]
            window['-PRODUCT-'].update(selected_product['Product Code'])
            window['-PROD_INFO-'].update(f"Description: {selected_product['Product Description']}")
            window['-SUPP_INFO-'].update(f"Supplier: {selected_product['Supplier Name']}")
            window['-DEPT_INFO-'].update(f"Department: {selected_product['Department']}")

        if event == 'Deliver':
            product_code = values['-PRODUCT-']
            quantity = values['-QUANTITY-']
            if product_code and quantity:
                product = deliver_product(df, product_code, quantity)
                inventory.append(product)
                window['-TABLE-'].update([[item['Product Code'], item['Product Description'], item['Batch/Lot'], item['Quantity'], item['Status']] for item in inventory])
                sg.popup('Product delivered successfully')
            else:
                sg.popup_error('Please enter both product code and quantity')

        if event == 'Process':
            if values['-TABLE-']:
                index = values['-TABLE-'][0]
                inventory[index] = process_product(inventory[index])
                window['-TABLE-'].update([[item['Product Code'], item['Product Description'], item['Batch/Lot'], item['Quantity'], item['Status']] for item in inventory])
                sg.popup('Product processed successfully')
            else:
                sg.popup_error('Please select a product to process')

        if event == 'View Inventory':
            view_detailed_inventory(inventory)

    window.close()

if __name__ == "__main__":
    df = load_data('Butchery reports Big G.csv')
    create_gui(df)
