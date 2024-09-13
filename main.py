import pandas as pd
import PySimpleGUI as sg
import csv
from fpdf import FPDF
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import io
from PIL import Image
from auth_system import AuthSystem

# Constants
FONT_HEADER = ('Helvetica', 30)
FONT_NORMAL = ('Helvetica', 18)
FONT_SMALL = ('Helvetica', 14)
PAD = (20, 10)

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
def deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date, auth_system):
    product = df[df['Product Code'] == product_code].iloc[0]
    batch_lot = f'LOT-{datetime.now().strftime("%Y%m%d")}-{product_code}'
    current_user = auth_system.get_current_user()
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
        'Handling History': f'Received at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} by {current_user}',
        'Quality Checks': 'Initial check: Passed',
        'Temperature Log': [],
        'Received By': current_user,
        'Processed By': '',
        'Delivery Approved By': '',
        'Delivery Approval Date': ''
    }

def approve_delivery(product, auth_system):
    current_user = auth_system.get_current_user()
    approval_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Status'] = 'Delivery Approved'
    product['Delivery Approved By'] = current_user
    product['Delivery Approval Date'] = approval_date
    product['Handling History'] += f"\nDelivery approved at {approval_date} by {current_user}"
    return product

def process_product(product, auth_system):
    current_user = auth_system.get_current_user()
    product['Status'] = 'Delivery Approved'
    product['Processing Date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Current Location'] = f"{product['Department']} - {product['Sub-Department']}"
    product['Handling History'] += f"\n        {product['Current Location']}"
    product['Quality Checks'] += f"\n        Pre-processing check: Passed"
    product['Processed By'] = current_user
    return product

# Barcode generation
def generate_barcode(data):
    code128 = barcode.get_barcode_class('code128')
    rv = io.BytesIO()
    code128(data, writer=ImageWriter()).write(rv)
    image = Image.open(rv)
    image.thumbnail((300, 300))
    return image

# New function for search suggestions
def get_search_suggestions(df, search_term):
    suggestions = df[df['Product Description'].str.contains(search_term, case=False, na=False)]['Product Description'].tolist()
    return suggestions[:10]  # Limit to 10 suggestions


# Modified create_input_column function
def create_input_column():
    current_date = datetime.now().strftime('%Y-%m-%d')
    return [
        [sg.Text('Search Description:', size=(15, 1)), 
         sg.Input(key='-SEARCH-', size=(30, 1), enable_events=True),
         sg.Button('Search', size=(10, 1))],
        [sg.Listbox(values=[], size=(30, 6), key='-SUGGESTIONS-', enable_events=True, visible=False)],
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
                  auto_size_columns=True,
                  col_widths=[15, 30, 20, 10, 5, 15],
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

def show_login_window(auth_system):
    layout = [
        [sg.Text('Username:'), sg.Input(key='-USERNAME-')],
        [sg.Text('Password:'), sg.Input(key='-PASSWORD-', password_char='*')],
        [sg.Button('Login'), sg.Button('Exit')]
    ]
    window = sg.Window('Login', layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            window.close()
            return False
        if event == 'Login':
            if auth_system.login(values['-USERNAME-'], values['-PASSWORD-']):
                sg.popup('Login successful!')
                window.close()
                return True
            else:
                sg.popup('Login failed. Please try again.')
    
        window.close()
        return False
        
    

# Modified create_gui function
def create_gui(df):
    auth_system = AuthSystem()
    # Add some users (in practice, this might be done separately)
    auth_system.add_user("john", "password123")
    auth_system.add_user("jane", "securepass456")

    while True:
        if not show_login_window(auth_system):
            return  # Exit if login fails or user cancels

        sg.theme('LightBlue2')  # Change theme for a fresh look

        # Search and Product Info Column
        left_column = [
            [sg.Frame('Search', [
    [sg.Text('Search Description:', size=(15, 1)), 
     sg.Input(key='-SEARCH-', size=(30, 1), enable_events=True),
     sg.Button('Search', size=(10, 1))],
    [sg.Listbox(values=[], size=(45, 6), key='-SUGGESTIONS-', enable_events=True, visible=False)]
])],
            [sg.Frame('Product Information', [
                [sg.Text('Product Code', size=(15, 1)), sg.Input(key='-PRODUCT-', size=(20, 1), enable_events=True)],
                [sg.Text('Supplier Product', size=(15, 1)), sg.Input(key='-SUPPLIER_PRODUCT-', size=(20, 1), enable_events=True)],
                [sg.Text('Description', size=(15, 1)), sg.Combo([], key='-PRODUCT_DESC-', size=(30, 1), enable_events=True)],
                [sg.Text('Quantity', size=(15, 1)), 
                 sg.Input(key='-QUANTITY-', size=(10, 1), enable_events=True),
                 sg.Combo(['unit', 'kg'], default_value='unit', key='-UNIT-', size=(5, 1), enable_events=True)],
                [sg.Text('Supplier Batch', size=(15, 1)), sg.Input(key='-SUPPLIER_BATCH-', size=(20, 1))],
                [sg.Text('Sell by Date', size=(15, 1)), 
                 sg.Input(key='-SELL_BY_DATE-', size=(10, 1), default_text=datetime.now().strftime('%Y-%m-%d')),
                 sg.CalendarButton('Select Date', target='-SELL_BY_DATE-', format='%Y-%m-%d')]
            ])],
            [sg.Frame('Actions', [
                [sg.Button('Receive Product', size=(15, 1), pad=PAD)],
                [sg.Button('View Inventory', size=(15, 1), pad=PAD)]
            ])],
        ]

        # Inventory Table Column
        right_column = [
            [sg.Table(values=[],
                      headings=['Product Code', 'Description', 'Quantity', 'Unit', 'Status'],
                      display_row_numbers=False,
                      auto_size_columns=True,
                      num_rows=15,
                      key='-TABLE-',
                      enable_events=True,
                      tooltip='Recently Received Products')],
            [sg.Button('Delivery Approved', size=(15, 1)), sg.Button('Generate Barcode', size=(15, 1))]
        ]

        # Main Layout
        layout = [
            [sg.Text('SPATRAC Inventory Management System', font=FONT_HEADER, justification='center', expand_x=True)],
            [sg.Column(left_column, vertical_alignment='top'), 
             sg.VSeperator(),
             sg.Column(right_column, vertical_alignment='top', expand_x=True, expand_y=True)],
            [sg.Button('Logout', size=(10, 1)), sg.Button('Exit', size=(10, 1))]
        ]

        window = sg.Window('SPATRAC', layout, finalize=True, resizable=True)
        window['-PRODUCT_DESC-'].update(values=df['Product Description'].tolist())

        inventory = []

        def update_fields(selected_product):
            window['-PRODUCT-'].update(selected_product['Product Code'])
            window['-SUPPLIER_PRODUCT-'].update(selected_product['Supplier Product Code'])
            window['-PRODUCT_DESC-'].update(selected_product['Product Description'])

        def clear_fields():
            window['-PRODUCT-'].update('')
            window['-SUPPLIER_PRODUCT-'].update('')
            window['-PRODUCT_DESC-'].update('')
            window['-QUANTITY-'].update('')

        last_input = {'key': None, 'value': None}

        while True:
            event, values = window.read(timeout=500)
            if event in (sg.WIN_CLOSED, 'Exit'):
                break

            if event == 'Logout':
                window.close()
                break  # Break the inner loop to go back to login

            # New event handling for search suggestions
            if event == '-SEARCH-':
                search_term = values['-SEARCH-']
                if search_term:
                    suggestions = get_search_suggestions(df, search_term)
                    window['-SUGGESTIONS-'].update(values=suggestions, visible=True)
                else:
                    window['-SUGGESTIONS-'].update(values=[], visible=False)

            if event == '-SUGGESTIONS-' and values['-SUGGESTIONS-']:
                selected_suggestion = values['-SUGGESTIONS-'][0]
                window['-SEARCH-'].update(value=selected_suggestion)
                window['-SUGGESTIONS-'].update(visible=False)
                selected_products = df[df['Product Description'] == selected_suggestion]
                if len(selected_products) == 1:
                    update_fields(selected_products.iloc[0])

            if event == 'Search':
                search_term = values['-SEARCH-']
                selected_products = df[df['Product Description'].str.contains(search_term, case=False, na=False)]
                if len(selected_products) == 1:
                    update_fields(selected_products.iloc[0])
                elif len(selected_products) > 1:
                    sg.popup_error("Multiple products found. Please be more specific.")
                    clear_fields()
                else:
                    sg.popup_error("No matching product found.")
                    clear_fields()

            if event in ('-PRODUCT-', '-SUPPLIER_PRODUCT-', '-PRODUCT_DESC-'):
                last_input['key'] = event
                last_input['value'] = values[event]

            elif event == '__TIMEOUT__' and last_input['value']:
                try:
                    if last_input['key'] == '-PRODUCT-':
                        selected_products = df[df['Product Code'] == last_input['value']]
                    elif last_input['key'] == '-SUPPLIER_PRODUCT-':
                        selected_products = df[df['Supplier Product Code'] == last_input['value']]
                    elif last_input['key'] == '-PRODUCT_DESC-':
                        selected_products = df[df['Product Description'] == last_input['value']]
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

            if event == 'Receive Product':
                product_code = values['-PRODUCT-']
                quantity = values['-QUANTITY-']
                unit = values['-UNIT-']
                supplier_batch = values['-SUPPLIER_BATCH-']
                sell_by_date = values['-SELL_BY_DATE-']

                if product_code and quantity and supplier_batch and sell_by_date:
                    product = deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date, auth_system)
                    temp_log = record_temperature_popup()
                    if temp_log:
                        product['Temperature Log'].append(temp_log)
                        sg.popup('Product received and temperature recorded successfully', font=FONT_NORMAL)
                    else:
                        sg.popup('Product received successfully (no temperature recorded)', font=FONT_NORMAL)
                    
                    inventory.append(product)
                    window['-TABLE-'].update([[item['Product Code'], item['Product Description'], item['Quantity'], item['Unit'], item['Status']] for item in inventory])
                else:
                    sg.popup_error('Please fill in all required fields', font=FONT_NORMAL)

            if event == 'Delivery Approved':
                selected_rows = values['-TABLE-']
                if selected_rows:
                    for idx in selected_rows:
                        if idx < len(inventory):
                            product = inventory[idx]
                            processed_product = process_product(product, auth_system)
                            inventory[idx] = processed_product
                    window['-TABLE-'].update([[item['Product Code'], item['Product Description'], item['Quantity'], item['Unit'], item['Status']] for item in inventory])
                    sg.popup('Selected products delivery successfully', font=FONT_NORMAL)
                else:
                    sg.popup_error('Please select products to process', font=FONT_NORMAL)

            if event == 'Generate Barcode':
                selected_rows = values['-TABLE-']
                if selected_rows:
                    for idx in selected_rows:
                        if idx < len(inventory):
                            generate_and_show_barcode(inventory[idx])
                else:
                    sg.popup_error('Please select a product to generate a barcode', font=FONT_NORMAL)

            if event == 'View Inventory':
                window.hide()
                view_detailed_inventory(inventory, auth_system)
                window.un_hide()

        window.close()

        sg.popup('Thank you for using SPATRAC Inventory Management System', font=FONT_NORMAL)

# Detailed inventory view
def view_detailed_inventory(inventory, auth_system):
    headings = ['Product Description', 'Department', 'Sub-Department', 'Quantity', 'Unit', 'Delivery Date', 'Status', 'Processing Date', 'Current Location']
    
    table_data = []
    for item in inventory:
        row = [
            item.get('Product Description', ''),
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
                  col_widths=[15, 15, 15, 10, 8, 15, 10, 15, 20],
                  num_rows=min(25, len(inventory)),
                  key='-INV_TABLE-',
                  enable_events=True,
                  font=FONT_SMALL,
                  justification='left',
                  select_mode=sg.TABLE_SELECT_MODE_EXTENDED)],
        [sg.Button('Select All', pad=PAD),
         sg.Button('Deselect All', pad=PAD),
         sg.Button('View Traceability Report', pad=PAD),
         sg.Button('Process', pad=PAD),
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
                if product['Status'] != 'Delivery Approved':
                    temp_log = record_temperature_popup()
                    if temp_log:
                        product['Temperature Log'].append(temp_log)
                        processed_product = process_product(product, auth_system)
                        inventory[selected_index] = processed_product
                        table_data[selected_index] = [
                            processed_product.get('Product Description', ''),
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
        - Received By: {item['Received By']}
        
        Processing Information:
        - Department: {item['Department']}
        - Sub-Department: {item['Sub-Department']}
        - Processing Date: {item['Processing Date']}
        - Current Status: {item['Status']}
        - Location: {item['Current Location']}
        - Processed By: {item['Processed By']}
        
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
        [sg.Text(item['Product Description'], font=FONT_NORMAL)],
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