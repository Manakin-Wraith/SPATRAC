import pandas as pd
import PySimpleGUI as sg
import csv
from fpdf import FPDF
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import io
from PIL import Image

# Constants
FONT_HEADER = ('Helvetica', 20)
FONT_NORMAL = ('Helvetica', 12)
FONT_SMALL = ('Helvetica', 10)
PAD = (10, 5)

# Load the data
def load_data(file_path):
    df = pd.read_csv(file_path, encoding='iso-8859-1', sep=';')
    df.columns = df.iloc[0]
    return df.iloc[1:].reset_index(drop=True)

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

# Product operations
def deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date):
    product = df[df['Product Code'] == product_code].iloc[0]
    batch_lot = f'LOT-{datetime.now().strftime("%Y%m%d")}-{product_code}'
    return {
        'Product Code': product_code,
        'Supplier Product Code': product['Supplier Product Code'],
        'Product Description': product['Product Description'],
        'Supplier': product['Supplier Name'],
        'Batch/Lot': batch_lot,
        'Supplier Batch No': supplier_batch,
        'Sell By Date': sell_by_date,
        'Department': product['Department'],
        'Sub-Department': SUB_DEPT_MAPPING.get(str(product['Sub-Department']), ('Unknown', 'Unknown'))[1],
        'Quantity': quantity,
        'Unit': unit,
        'Delivery Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Status': 'Delivered',
        'Processing Date': '',
        'Current Location': 'Receiving',
        'Handling History': f'Received at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        'Quality Checks': 'Initial check: Passed',
        'Temperature Log': []
    }

def process_product(product):
    product['Status'] = 'Processed'
    product['Processing Date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Current Location'] = f"{product['Department']} - {product['Sub-Department']}"
    product['Handling History'] += f"\nMoved to {product['Current Location']} at {product['Processing Date']}"
    product['Quality Checks'] += f"\nPre-processing check: Passed"
    return product

# Barcode generation
def generate_barcode(data):
    code128 = barcode.get_barcode_class('code128')
    rv = io.BytesIO()
    code128(data, writer=ImageWriter()).write(rv)
    image = Image.open(rv)
    image.thumbnail((300, 300))
    return image

# GUI Components
def create_input_column():
    current_date = datetime.now().strftime('%Y-%m-%d')
    return [
        [sg.Text('Search Description:', size=(15, 1)), sg.Input(key='-SEARCH-', size=(30, 1)), sg.Button('Search', size=(10, 1))],
        [sg.HorizontalSeparator()],
        [sg.Text('Product Code', size=(15, 1)), sg.Input(key='-PRODUCT-', size=(20, 1), enable_events=True)],
        [sg.Text('Supplier Product Code', size=(15, 1)), sg.Input(key='-SUPPLIER_PRODUCT-', size=(20, 1), enable_events=True)],
        [sg.Text('Product Description', size=(15, 1)), sg.Combo([], key='-PRODUCT_DESC-', size=(30, 1), enable_events=True)],
        [sg.Text('Quantity', size=(15, 1)), 
         sg.Input(key='-QUANTITY-', size=(10, 1), enable_events=True),
         sg.Combo(['unit', 'kg'], default_value='unit', key='-UNIT-', size=(5, 1), enable_events=True)],
        [sg.Text('Supplier Batch Code', size=(15, 1)), sg.Input(key='-SUPPLIER_BATCH-', size=(20, 1))],
        [sg.Text('Sell by Date', size=(15, 1)), 
         sg.Input(key='-SELL_BY_DATE-', size=(10, 1), default_text=current_date),
         sg.CalendarButton('Select Date', target='-SELL_BY_DATE-', format='%Y-%m-%d')],
        [sg.Column([
            [sg.Button('Received', size=(15, 1), pad=PAD)],
            [sg.Button('View Inventory', size=(15, 1), pad=PAD)]
        ], element_justification='left')],
        [sg.HorizontalSeparator()],
        [sg.Text('Product Information', font=FONT_HEADER, pad=PAD)],
        [sg.Text('', size=(40, 1), key='-PROD_INFO-', font=FONT_NORMAL)],
        [sg.Text('', size=(40, 1), key='-SUPP_INFO-', font=FONT_NORMAL)],
        [sg.Text('', size=(40, 1), key='-DEPT_INFO-', font=FONT_NORMAL)],
        [sg.Text('Quantity:', size=(15, 1)), sg.Text('', size=(25, 1), key='-QUANTITY_DISPLAY-')],
        [sg.Text('', size=(40, 1), key='-TEMP_INFO-', font=FONT_NORMAL)],
    ]

def create_table_column():
    return [
        [sg.Table(values=[],
                  headings=['Product Code', 'Description', 'Batch/Lot', 'Quantity', 'Unit', 'Status'],
                  display_row_numbers=False,
                  auto_size_columns=False,
                  col_widths=[15, 40, 20, 10, 5, 10],
                  num_rows=15,
                  key='-TABLE-',
                  font=FONT_SMALL,
                  justification='left',
                  enable_events=True)]  # Added enable_events=True
    ]

# Record temperature
def record_temperature_popup():
    locations = [
        'Receiving', 'Hot Foods', 'Butchery', 'Bakery', 'Fruit & Veg',
        'Admin', 'Coffee shop', 'Floor', 'Location 9', 'Location 10', 'Location 11'
    ]
    
    layout = [
        [sg.Text('Record Temperature', font=FONT_NORMAL)],
        [sg.Text('Temperature:', font=FONT_NORMAL), sg.Input(key='-TEMP-', font=FONT_NORMAL)],
        [sg.Text('Location:', font=FONT_NORMAL), 
         sg.Combo(locations, default_value=locations[0], key='-LOCATION-', font=FONT_NORMAL, readonly=True)],
        [sg.Button('Submit', font=FONT_NORMAL), sg.Button('Cancel', font=FONT_NORMAL)]
    ]
    
    window = sg.Window('Record Temperature', layout)
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            window.close()
            return None
        if event == 'Submit':
            try:
                temp = float(values['-TEMP-'])
                location = values['-LOCATION-']
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                window.close()
                return f"{timestamp}: {temp}°C at {location}"
            except ValueError:
                sg.popup_error('Please enter a valid temperature', font=FONT_NORMAL)
    
    window.close()

# Main GUI
def create_gui(df):
    sg.theme('LightGrey1')

    layout = [
        [sg.Column(create_input_column(), pad=PAD), 
         sg.VSeparator(),
         sg.Column(create_table_column(), pad=PAD)]
    ]

    window = sg.Window('Inventory Management System', layout, finalize=True, resizable=True)
    window['-PRODUCT_DESC-'].update(values=df['Product Description'].tolist())

    inventory = []

    def update_fields(selected_product):
     window['-PRODUCT-'].update(selected_product['Product Code'])
     window['-SUPPLIER_PRODUCT-'].update(selected_product['Supplier Product Code'])
     window['-PRODUCT_DESC-'].update(selected_product['Product Description'])
     window['-PROD_INFO-'].update(f"Description: {selected_product['Product Description']}")
     window['-SUPP_INFO-'].update(f"Supplier: {selected_product['Supplier Name']}")
     window['-DEPT_INFO-'].update(f"Department: {selected_product['Department']}")
    

    def clear_fields():
        window['-PRODUCT-'].update('')
        window['-SUPPLIER_PRODUCT-'].update('')
        window['-PRODUCT_DESC-'].update('')
        window['-PROD_INFO-'].update('')
        window['-SUPP_INFO-'].update('')
        window['-DEPT_INFO-'].update('')
        window['-QUANTITY-'].update('')
        window['-QUANTITY_DISPLAY-'].update('')

    last_input = {'key': None, 'value': None}

    while True:
        event, values = window.read(timeout=500)
        if event == sg.WIN_CLOSED:
            break

        if event in ('-QUANTITY-', '-UNIT-'):
            quantity = values['-QUANTITY-']
            unit = values['-UNIT-']
            window['-QUANTITY_DISPLAY-'].update(f"{quantity} {unit}" if quantity else "")

        if event in ('-PRODUCT-', '-SUPPLIER_PRODUCT-'):
            last_input['key'] = event
            last_input['value'] = values[event]
        elif event == '-PRODUCT_DESC-' and values['-PRODUCT_DESC-']:
            try:
                selected_products = df[df['Product Description'] == values['-PRODUCT_DESC-']]
                if len(selected_products) == 1:
                    update_fields(selected_products.iloc[0])
                elif len(selected_products) > 1:
                    sg.popup_error("Multiple products found. Please be more specific.")
                    clear_fields()
                else:
                    sg.popup_error("No matching product found.")
                    clear_fields()
            except Exception as e:
                sg.popup_error(f"An error occurred: {str(e)}")
                clear_fields()
        elif event == '__TIMEOUT__' and last_input['value']:
            try:
                if last_input['key'] == '-PRODUCT-':
                    selected_products = df[df['Product Code'] == last_input['value']]
                elif last_input['key'] == '-SUPPLIER_PRODUCT-':
                    selected_products = df[df['Supplier Product Code'] == last_input['value']]
                else:
                    continue

                if len(selected_products) == 1:
                    update_fields(selected_products.iloc[0])
                elif len(selected_products) > 1:
                    sg.popup_error("Multiple products found. Please be more specific.")
                    clear_fields()
                elif last_input['value']:
                    sg.popup_error("No matching product found.")
                    clear_fields()

                last_input = {'key': None, 'value': None}
            except Exception as e:
                sg.popup_error(f"An error occurred: {str(e)}")
                clear_fields()


        if event == 'Received':
            product_code = values['-PRODUCT-']
            quantity = values['-QUANTITY-']
            unit = values['-UNIT-']
            supplier_batch = values['-SUPPLIER_BATCH-']
            sell_by_date = values['-SELL_BY_DATE-']

            if product_code and quantity and supplier_batch and sell_by_date:
               product = deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date)
        
               # Open temperature recording popup
               temp_log = record_temperature_popup()
               if temp_log:
                   product['Temperature Log'].append(temp_log)
                   sg.popup('Product delivered and temperature recorded successfully', font=FONT_NORMAL)
               else:
                   sg.popup('Product delivered successfully (no temperature recorded)', font=FONT_NORMAL)
        
               inventory.append(product)
               window['-TABLE-'].update([[item['Product Code'], item['Product Description'], item['Batch/Lot'], item['Quantity'], item['Unit'], item['Status']] for item in inventory])
            else:
                sg.popup_error('Please fill in all required fields', font=FONT_NORMAL)

    
        if event == 'Process':
            selected_rows = values['-TABLE-']
            if selected_rows:
                selected_index = selected_rows[0]
                if selected_index < len(inventory):
                    product = inventory[selected_index]
                    processed_product = process_product(product)
                    inventory[selected_index] = processed_product
                    window['-TABLE-'].update([[item['Product Code'], item['Product Description'], item['Batch/Lot'], item['Quantity'], item['Unit'], item['Status']] for item in inventory])
                    sg.popup('Product processed successfully', font=FONT_NORMAL)
                else:
                    sg.popup_error('Invalid selection', font=FONT_NORMAL)
            else:
                sg.popup_error('Please select a product to process', font=FONT_NORMAL)

        if event == 'Record Temperature':
            selected_rows = values['-TABLE-']
            if selected_rows:
                selected_index = selected_rows[0]
                if selected_index < len(inventory):
                    record_temperature(inventory[selected_index])
                    window['-TABLE-'].update([[item['Product Code'], item['Product Description'], item['Batch/Lot'], item['Quantity'], item['Unit'], item['Status']] for item in inventory])
                else:
                    sg.popup_error('Invalid selection', font=FONT_NORMAL)
            else:
                sg.popup_error('Please select a product to record temperature', font=FONT_NORMAL)        

        if event == 'View Inventory':
            view_detailed_inventory(inventory)

    window.close()

# Detailed inventory view
def view_detailed_inventory(inventory):
    headings = ['Product Code', 'Supplier Product Code', 'Description', 'Supplier', 'Batch/Lot', 'Supplier Batch No', 'Sell By Date', 'Department', 'Sub-Department', 'Quantity', 'Unit', 'Delivery Date', 'Status', 'Processing Date', 'Current Location']
    
    table_data = []
    for item in inventory:
        row = [
            item.get('Product Code', ''),
            item.get('Supplier Product Code', ''),
            item.get('Product Description', ''),
            item.get('Supplier', ''),
            item.get('Batch/Lot', ''),
            item.get('Supplier Batch No', ''),
            item.get('Sell By Date', ''),
            item.get('Department', ''),
            item.get('Sub-Department', ''),
            item.get('Quantity', ''),
            item.get('Unit', ''),
            item.get('Delivery Date', ''),
            item.get('Status', ''),
            item.get('Processing Date', ''),
            item.get('Current Location', '')
        ]
        table_data.append(row)
    
    layout = [
        [sg.Text('Detailed Inventory', font=FONT_HEADER, pad=PAD)],
        [sg.Table(values=table_data,
                  headings=headings,
                  display_row_numbers=False,
                  auto_size_columns=False,
                  col_widths=[12, 12, 30, 20, 15, 15, 15, 10, 5, 20, 10, 20, 15],
                  num_rows=min(25, len(inventory)),
                  key='-INV_TABLE-',
                  enable_events=True,
                  font=FONT_SMALL,
                  justification='left',
                  select_mode=sg.TABLE_SELECT_MODE_EXTENDED)],
        [sg.Button('Select All', pad=PAD),
         sg.Button('Deselect All', pad=PAD),
         sg.Button('View Traceability Report', pad=PAD), 
         sg.Button('Process', pad=PAD),  # Changed from 'Record Temperature' to 'Process'
         sg.Button('Generate Barcode', pad=PAD), 
         sg.Button('Close', pad=PAD)]
    ]

    window = sg.Window('Detailed Inventory', layout, resizable=True, size=(1300, 600))

    selected_rows = set()

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == 'Close':
            break

        if event == '-INV_TABLE-':
            selected_rows = set(values['-INV_TABLE-'])

        if event == 'Select All':
            window['-INV_TABLE-'].update(select_rows=list(range(len(table_data))))
            selected_rows = set(range(len(table_data)))

        if event == 'Deselect All':
            window['-INV_TABLE-'].update(select_rows=[])
            selected_rows = set()

        if event == 'View Traceability Report':
            if selected_rows:
                selected_items = [inventory[i] for i in selected_rows]
                show_traceability_report(selected_items)
            else:
                sg.popup_error('Please select at least one product to view its traceability report.')
            
        elif event == 'Process':
            if values['-INV_TABLE-']:
                selected_index = values['-INV_TABLE-'][0]
                product = inventory[selected_index]
                if product['Status'] != 'Processed':
                    temp_log = record_temperature_popup()
                    if temp_log:
                        product['Temperature Log'].append(temp_log)
                        processed_product = process_product(product)
                        inventory[selected_index] = processed_product
                        table_data[selected_index] = [
                            processed_product.get('Product Code', ''),
                            processed_product.get('Supplier Product Code', ''),
                            processed_product.get('Product Description', ''),
                            processed_product.get('Supplier', ''),
                            processed_product.get('Batch/Lot', ''),
                            processed_product.get('Department', ''),
                            processed_product.get('Sub-Department', ''),
                            processed_product.get('Quantity', ''),
                            processed_product.get('Unit', ''),
                            processed_product.get('Delivery Date', ''),
                            processed_product.get('Status', ''),
                            processed_product.get('Processing Date', ''),
                            processed_product.get('Current Location', '')
                        ]
                        window['-INV_TABLE-'].update(table_data)
                        sg.popup('Product processed and temperature recorded successfully', font=FONT_NORMAL)
                else:
                    sg.popup('This product has already been processed', font=FONT_NORMAL)
            else:
                sg.popup_error('Please select a product', font=FONT_NORMAL)

        elif event == 'Generate Barcode':
            if values['-INV_TABLE-']:
                generate_and_show_barcode(inventory[values['-INV_TABLE-'][0]])
            else:
                sg.popup_error('Please select a product', font=FONT_NORMAL)

    window.close()

def show_traceability_report(items):
    report = generate_report_text(items)
    
    layout = [
        [sg.Multiline(report, size=(100, 40), font=FONT_NORMAL, key='-REPORT-')],
        [sg.Button('Save as PDF', key='-PDF-'), sg.Button('Save as CSV', key='-CSV-'), sg.Button('Close')]
    ]
    
    window = sg.Window('Traceability Report', layout, finalize=True)
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
        elif event == '-PDF-':
            save_as_pdf(report)
        elif event == '-CSV-':
            save_as_csv(items)
    
    window.close()

def generate_report_text(items):
    report = ""
    for item in items:
        report += f"""
        Traceability Report for Product: {item['Product Description']}
        -----------------------------------------------------
        Product Code: {item['Product Code']}
        Supplier Product Code: {item['Supplier Product Code']}
        Supplier: {item['Supplier']}
        Batch/Lot Number: {item['Batch/Lot']}
        Supplier Batch No: {item['Supplier Batch No']}
        Sell By Date: {item['Sell By Date']}
        
        Delivery Information:
        - Delivery Date: {item['Delivery Date']}
        - Quantity Received: {item['Quantity']} {item['Unit']}
        
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
        
        ======================================================
        
        """
    return report

def save_as_pdf(report):
    filename = sg.popup_get_file('Save PDF as', save_as=True, file_types=(("PDF Files", "*.pdf"),))
    if filename:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, report)
        pdf.output(filename)
        sg.popup(f"Report saved as {filename}")

def save_as_csv(items):
    filename = sg.popup_get_file('Save CSV as', save_as=True, file_types=(("CSV Files", "*.csv"),))
    if filename:
        with open(filename, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=items[0].keys())
            writer.writeheader()
            writer.writerows(items)
        sg.popup(f"Report saved as {filename}")
# Record temperature
def record_temperature(item):
    layout = [
        [sg.Text('Record Temperature', font=FONT_NORMAL)],
        [sg.Input(key='-TEMP-', font=FONT_NORMAL)],
        [sg.Text('Location:', font=FONT_NORMAL), sg.Input(key='-LOCATION-', font=FONT_NORMAL)],
        [sg.Button('Submit', font=FONT_NORMAL), sg.Button('Cancel', font=FONT_NORMAL)]
    ]
    window = sg.Window('Record Temperature', layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        if event == 'Submit':
            try:
                temp = float(values['-TEMP-'])
                location = values['-LOCATION-'] or 'Unknown'
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                item['Temperature Log'].append(f"{timestamp}: {temp}°C at {location}")
                sg.popup('Temperature recorded successfully', font=FONT_NORMAL)
                break
            except ValueError:
                sg.popup_error('Please enter a valid temperature', font=FONT_NORMAL)
    window.close()

# Generate and show barcode
def generate_and_show_barcode(item):
    # Combine Batch/Lot with Supplier Batch No
    combined_batch = f"{item['Batch/Lot']}-{item['Supplier Batch No']}"
    barcode_image = generate_barcode(combined_batch)
    
    # Convert image to bytes for PySimpleGUI
    bio = io.BytesIO()
    barcode_image.save(bio, format="PNG")
    barcode_data = bio.getvalue()
    
    layout = [
        [sg.Text(f"Barcode for {item['Product Description']}", font=FONT_NORMAL)],
        [sg.Image(data=barcode_data, key='-IMAGE-')],
        [sg.Button('Save Barcode', font=FONT_NORMAL), sg.Button('Close', font=FONT_NORMAL)]
    ]
    window = sg.Window('Barcode', layout)
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == 'Close':
            break
        elif event == 'Save Barcode':
            save_barcode(barcode_image, item)
    window.close()

def save_barcode(image, item):
    filename = sg.popup_get_file('Save Barcode as PNG', save_as=True, file_types=(("PNG Files", "*.png"),))
    if filename:
        if not filename.lower().endswith('.png'):
            filename += '.png'
        image.save(filename)
        sg.popup(f"Barcode saved as {filename}")

if __name__ == "__main__":
    df = load_data('Butchery reports Big G.csv')
    create_gui(df)