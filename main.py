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
FONT_HEADER = ('Helvetica', 24)
FONT_SUBHEADER = ('Helvetica', 18)
FONT_NORMAL = ('Helvetica', 12)
FONT_SMALL = ('Helvetica', 10)
PAD = (10, 5)
COLORS = {
    'primary': '#1a73e8',
    'secondary': '#f1f3f4',
    'text': '#202124',
    'success': '#0f9d58',
    'warning': '#f4b400',
    'error': '#d93025'
}

# Load the data
def load_data(file_paths):
    dfs = []
    required_columns = [
        "Supp. Cd.", "Supplier Name", "Sub-Department", 
        "Supplier Product Code", "Product Code", "Product Description"
    ]
    
    for file_path in file_paths:
        df = pd.read_csv(file_path, encoding='iso-8859-1', sep=';')
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        df = df[required_columns]
        department = file_path.split()[0].lower()
        df['Department'] = department
        dfs.append(df)
    
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df['unique_id'] = [f"row_{i}" for i in range(len(combined_df))]
    combined_df.set_index('unique_id', inplace=True, drop=False)
    
    return combined_df

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
        'Department': product['Department'].strip(),
        'Sub-Department': SUB_DEPT_MAPPING.get(str(product['Sub-Department']), ('Unknown', 'Unknown'))[1].strip(),
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
    processing_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Status'] = 'Processed'
    product['Processing Date'] = processing_date
    product['Current Location'] = f"{product['Department']} - {product['Sub-Department']}"
    product['Handling History'] += f"\nProcessed at {processing_date} by {current_user}"
    product['Quality Checks'] += f"\nPre-processing check: Passed"
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
    return suggestions[:10]

# Modified create_gui function
def create_gui(df):
    auth_system = AuthSystem()
    auth_system.add_user("john", "password123", "Delivery", "Manager")
    auth_system.add_user("jane", "securepass456", "Bakery", "Manager")
    auth_system.add_user("bob", "manager789", "Butchery", "Manager")
    auth_system.add_user("alice", "admin321", "HMR", "Manager")

    sg.theme('LightGrey1')
    sg.set_options(font=FONT_NORMAL)

    while True:
        if not show_login_window(auth_system):
            return

        user_info = auth_system.get_current_user_info()
        user_info_text = f"User: {user_info['username']} | Role: {user_info['role']} | Department: {user_info['department']}"

        departments = ['Butchery', 'Bakery', 'HMR']

        layout = [
            [sg.Text('SPATRAC Inventory Management System', font=FONT_HEADER, justification='center', expand_x=True, pad=((0, 0), (20, 20)))],
            [sg.Text(user_info_text, font=FONT_SMALL, justification='right', expand_x=True, pad=((0, 0), (0, 20)))],
            [sg.TabGroup([
                [sg.Tab('Product Management', create_product_management_tab(df, departments)),
                 sg.Tab('Inventory', create_inventory_tab()),
                 sg.Tab('Reports', create_reports_tab())]
            ], key='-TABGROUP-', expand_x=True, expand_y=True)],
            [sg.Button('Logout', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('Exit', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']))]
        ]

        window = sg.Window('SPATRAC', layout, finalize=True, resizable=True, size=(1200, 800))
        
        inventory = []

        while True:
            event, values = window.read(timeout=100)
            if event in (sg.WIN_CLOSED, 'Exit'):
                return
            if event == 'Logout':
                auth_system.logout()
                window.close()
                break

            handle_product_management_events(event, values, window, df, inventory, auth_system)
            handle_inventory_events(event, values, window, inventory, auth_system)
            handle_reports_events(event, values, window, inventory, auth_system)  # Added auth_system

        window.close()

def create_product_management_tab(df, departments):
    all_product_descriptions = sorted(df['Product Description'].unique().tolist())
    
    department_frames = []
    for dept in departments:
        frame_layout = [
            [sg.Table(values=[],
                      headings=['Product Code', 'Description', 'Quantity', 'Unit', 'Status'],
                      display_row_numbers=False,
                      auto_size_columns=True,
                      num_rows=5,
                      key=f'-{dept.upper()}_TABLE-',
                      enable_events=True)]
        ]
        department_frames.append(sg.Frame(f'{dept} Window', frame_layout, key=f'-{dept.upper()}_FRAME-'))

    return [
        [sg.Frame('Product Selection', [
            [sg.Text('Product Description:', size=(15, 1)),
             sg.Combo(all_product_descriptions, key='-PRODUCT_DESC-', size=(40, 1), enable_events=True)],
            [sg.Text('Search (Optional):', size=(15, 1)),
             sg.Input(key='-SEARCH-', size=(30, 1), enable_events=True),
             sg.Button('Search', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']))],
            [sg.Listbox(values=[], size=(55, 6), key='-SUGGESTIONS-', enable_events=True, visible=False)],
            [sg.Text('Department', size=(15, 1)), 
             sg.Input(key='-DEPARTMENT-', size=(20, 1), readonly=True, text_color='white', background_color='#64778d')],
            [sg.Text('Product Code', size=(15, 1)), 
             sg.Input(key='-PRODUCT-', size=(20, 1), readonly=True, text_color='white', background_color='#64778d')],
            [sg.Text('Supplier Product', size=(15, 1)), 
             sg.Input(key='-SUPPLIER_PRODUCT-', size=(20, 1), readonly=True, text_color='white', background_color='#64778d')],
            [sg.Text('Quantity', size=(15, 1)),
             sg.Input(key='-QUANTITY-', size=(10, 1)),
             sg.Combo(['unit', 'kg'], default_value='unit', key='-UNIT-', size=(5, 1))],
            [sg.Text('Supplier Batch', size=(15, 1)), sg.Input(key='-SUPPLIER_BATCH-', size=(20, 1))],
            [sg.Text('Sell by Date', size=(15, 1)),
             sg.Input(key='-SELL_BY_DATE-', size=(10, 1), default_text=datetime.now().strftime('%Y-%m-%d')),
             sg.CalendarButton('Select Date', target='-SELL_BY_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['secondary']))],
            [sg.Button('Receive Product', size=(15, 1), button_color=(COLORS['text'], COLORS['primary']))],
        ], relief=sg.RELIEF_SUNKEN, expand_x=True, expand_y=True)],
        department_frames
    ]

def create_inventory_tab():
    return [
        [sg.Frame('Inventory Overview', [
            [sg.Table(values=[],
                      headings=['Department', 'Product Code', 'Description', 'Quantity', 'Unit', 'Status'],
                      display_row_numbers=False,
                      auto_size_columns=True,
                      num_rows=15,
                      key='-INVENTORY_TABLE-',
                      enable_events=True)]
        ], relief=sg.RELIEF_SUNKEN, expand_x=True, expand_y=True)],
        [sg.Button('View Details', size=(15, 1), button_color=(COLORS['text'], COLORS['secondary'])),
         sg.Button('Process Selected', size=(15, 1), button_color=(COLORS['text'], COLORS['secondary'])),
         sg.Button('Generate Barcode', size=(15, 1), button_color=(COLORS['text'], COLORS['secondary']))]
    ]


def create_reports_tab():
    return [
        [sg.Frame('Generate Reports', [
            [sg.Text('Report Type:'),
             sg.Combo(['Traceability', 'Inventory Summary', 'Temperature Log'], key='-REPORT_TYPE-', size=(20, 1))],
            [sg.Text('Date Range:'),
             sg.Input(key='-START_DATE-', size=(10, 1)),
             sg.CalendarButton('Start Date', target='-START_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Input(key='-END_DATE-', size=(10, 1)),
             sg.CalendarButton('End Date', target='-END_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['secondary']))],
            [sg.Button('Generate Report', size=(15, 1), button_color=(COLORS['text'], COLORS['primary']))]
        ], relief=sg.RELIEF_SUNKEN, expand_x=True, expand_y=True)],
        [sg.Frame('Report Preview', [
            [sg.Multiline(size=(80, 20), key='-REPORT_PREVIEW-', disabled=True)]
        ], relief=sg.RELIEF_SUNKEN, expand_x=True, expand_y=True)],
        [sg.Button('Save as PDF', size=(15, 1), button_color=(COLORS['text'], COLORS['secondary'])),
         sg.Button('Save as CSV', size=(15, 1), button_color=(COLORS['text'], COLORS['secondary']))]
    ]

def create_department_window(department, processed_products, final_products):
    layout = [
        [sg.Text(f"{department} Processed Products", font=FONT_SUBHEADER)],
        [sg.Table(values=processed_products,
                  headings=['Product Code', 'Description', 'Quantity', 'Unit'],
                  display_row_numbers=False,
                  auto_size_columns=True,
                  num_rows=10,
                  key='-PROCESSED_TABLE-',
                  enable_events=True)],
        [sg.Text("Matched Final Products", font=FONT_SUBHEADER)],
        [sg.Table(values=[],
                  headings=['Final Product Code', 'Final Product Name', 'Ingredient Code', 'Ingredient Description', 'Required Quantity'],
                  display_row_numbers=False,
                  auto_size_columns=True,
                  num_rows=10,
                  key='-MATCHED_TABLE-')],
        [sg.Button('Match Products', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Close', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    return sg.Window(f"{department} Processing", layout, finalize=True)

def get_search_suggestions(df, search_term):
    suggestions = df[df['Product Description'].str.contains(search_term, case=False, na=False)]['Product Description'].tolist()
    return suggestions[:10]  # Limit to top 10 suggestions

def handle_product_management_events(event, values, window, df, inventory, auth_system):
    if event == '-SEARCH-':
        search_term = values['-SEARCH-']
        if search_term:
            suggestions = get_search_suggestions(df, search_term)
            window['-SUGGESTIONS-'].update(values=suggestions, visible=True)
        else:
            window['-SUGGESTIONS-'].update(values=[], visible=False)

    if event == '-SUGGESTIONS-':
        if values['-SUGGESTIONS-']:
            selected_product = values['-SUGGESTIONS-'][0]
            window['-PRODUCT_DESC-'].update(value=selected_product)
            window['-SUGGESTIONS-'].update(visible=False)
            product_info = df[df['Product Description'] == selected_product].iloc[0]
            window['-DEPARTMENT-'].update(product_info['Department'])
            window['-PRODUCT-'].update(product_info['Product Code'])
            window['-SUPPLIER_PRODUCT-'].update(product_info['Supplier Product Code'])
    if event == '-PRODUCT_DESC-':
        selected_product = values['-PRODUCT_DESC-']
        if selected_product:
            product_info = df[df['Product Description'] == selected_product].iloc[0]
            window['-DEPARTMENT-'].update(product_info['Department'])
            window['-PRODUCT-'].update(product_info['Product Code'])
            window['-SUPPLIER_PRODUCT-'].update(product_info['Supplier Product Code'])

    if event == 'Search':
        search_term = values['-SEARCH-']
        if search_term:
            suggestions = get_search_suggestions(df, search_term)
            window['-PRODUCT_DESC-'].update(values=suggestions)
        else:
            all_product_descriptions = sorted(df['Product Description'].unique().tolist())
            window['-PRODUCT_DESC-'].update(values=all_product_descriptions)        

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
            
            inventory.append(product)
            update_inventory_table(window, inventory)
            update_department_tables(window, inventory)
            sg.popup('Product received successfully', font=FONT_NORMAL)
        else:
            sg.popup_error('Please fill in all required fields', font=FONT_NORMAL)

# Add a new function to update department-specific tables
def update_department_tables(window, inventory):
    departments = ['HMR', 'Butchery', 'Bakery']
    for dept in departments:
        dept_inventory = [item for item in inventory if item['Department'].lower() == dept.lower()]
        window[f'-{dept.upper()}_TABLE-'].update([
            [item['Product Code'], item['Product Description'], item['Quantity'], item['Unit'], item['Status']]
            for item in dept_inventory
        ])

def handle_inventory_events(event, values, window, inventory, auth_system):
    if event == 'View Details':
        selected_rows = values['-INVENTORY_TABLE-']
        if selected_rows:
            selected_product = inventory[selected_rows[0]]
            show_product_details(selected_product, auth_system)
        else:
            sg.popup_error('Please select a product to view details', font=FONT_NORMAL)

    if event == 'Process Selected':
        selected_rows = values['-INVENTORY_TABLE-']
        if selected_rows:
            user_info = auth_system.get_current_user_info()
            if user_info is None:
                sg.popup_error('Error: No user is currently logged in.', font=FONT_NORMAL)
            elif user_info['role'] != 'Manager':
                sg.popup_error('You are not authorized to process products. Only Managers can process products.', font=FONT_NORMAL)
            else:
                process_selected_products(auth_system, inventory, selected_rows, window)
        else:
            sg.popup_error('Please select products to process', font=FONT_NORMAL)

    if event == 'Generate Barcode':
        selected_rows = values['-INVENTORY_TABLE-']
        if selected_rows:
            selected_product = inventory[selected_rows[0]]
            generate_and_show_barcode(selected_product)
        else:
            sg.popup_error('Please select a product to generate a barcode', font=FONT_NORMAL)


def department_login_window(auth_system, inventory, selected_rows, main_window):
    layout = [
        [sg.Text('Department Manager Login', font=FONT_SUBHEADER)],
        [sg.Text('Username:', size=(15, 1)), sg.Input(key='-USERNAME-')],
        [sg.Text('Password:', size=(15, 1)), sg.Input(key='-PASSWORD-', password_char='*')],
        [sg.Button('Login', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Cancel', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    window = sg.Window('Department Manager Login', layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        if event == 'Login':
            username = values['-USERNAME-']
            password = values['-PASSWORD-']
            if auth_system.login(username, password):
                window.close()
                process_selected_products(auth_system, inventory, selected_rows, main_window)
                auth_system.logout()
                return
            else:
                sg.popup_error('Login failed. Please try again.')

    window.close()

def process_selected_products(auth_system, inventory, selected_rows, window):
    user_info = auth_system.get_current_user_info()
    if user_info is None:
        sg.popup_error('Error: No user is currently logged in.', font=FONT_NORMAL)
        return

    if user_info['role'] != 'Manager':
        sg.popup_error('You are not authorized to process products. Only Managers can process products.', font=FONT_NORMAL)
        return

    processed_products = []
    for idx in selected_rows:
        product = inventory[idx]
        if product['Status'] != 'Processed' and auth_system.is_authorized(user_info['username'], product['Department']):
            processed_product = process_product(product, auth_system)
            processed_product['Processed By'] = f"{user_info['username']} ({user_info['role']})"
            inventory[idx] = processed_product
            processed_products.append([
                processed_product['Product Code'],
                processed_product['Product Description'],
                processed_product['Quantity'],
                processed_product['Unit']
            ])
    
    update_inventory_table(window, inventory)
    update_department_tables(window, inventory)
    
    if processed_products:
        department = user_info['department']
        final_products = load_final_products(department)
        dept_window = create_department_window(department, processed_products, final_products)
        handle_department_window(dept_window, processed_products, final_products)
    
        sg.popup('Selected products processed successfully', font=FONT_NORMAL)

    else:
        sg.popup_error('You are not authorized to process products', font=FONT_NORMAL)

def load_final_products(department):
    # This is a placeholder. In a real application, you would load this data from a database or file.
    final_products = {
        'HMR': [
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '22585', 'SPAR SC CHS GRILLR F/LONG', '1'],
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '26734', 'SOFT HOTDOG ROLLS', '1'],
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '28442', 'GARLIC MAYO', '0.02'],
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '26221', 'SPAR SC RUSTIC ST/H CHIPS', '0.06'],
        ],
        'BUTCHERY': [
            ['26665', 'BABALAS BRAAI WORS', '28557', 'CHICKEN MDM', '25'],
            ['26665', 'BABALAS BRAAI WORS', '28760', 'BEEF KIDNEY FAT', '25'],
            ['26665', 'BABALAS BRAAI WORS', '29030', 'SPAR WATER', '30'],
            ['26665', 'BABALAS BRAAI WORS', '30590', 'PARTY BRAAIWORS', '15'],
        ],
        'BAKERY': [
            ['26710', 'WHITE BREAD', '15736', 'W/CAPE MILL MIX WHT BRD', '47.5'],
            ['26710', 'WHITE BREAD', '28779', 'YEAST WET', '1'],
            ['26710', 'WHITE BREAD', '29030', 'SPAR WATER', '24.7'],
        ]
    }
    return final_products.get(department.upper(), [])


def handle_department_window(window, processed_products, final_products):
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
        elif event == 'Match Products':
            matched_products = match_products(processed_products, final_products)
            window['-MATCHED_TABLE-'].update(matched_products)
    window.close()

def match_products(processed_products, final_products):
    matched = []
    for final_product in final_products:
        for processed in processed_products:
            if processed[0] == final_product[3]:  # Match on ingredient code
                matched.append(final_product)
    return matched


def handle_reports_events(event, values, window, inventory, auth_system):  # Added auth_system parameter
    if event == 'Generate Report':
        report_type = values['-REPORT_TYPE-']
        start_date = values['-START_DATE-']
        end_date = values['-END_DATE-']
        
        if report_type and start_date and end_date:
            report = generate_report(inventory, report_type, start_date, end_date, auth_system)  # Pass auth_system
            window['-REPORT_PREVIEW-'].update(report)
        else:
            sg.popup_error('Please select report type and date range', font=FONT_NORMAL)

    if event == 'Save as PDF':
        report = values['-REPORT_PREVIEW-']
        if report:
            save_as_pdf(report)
        else:
            sg.popup_error('Please generate a report first', font=FONT_NORMAL)

    if event == 'Save as CSV':
        report = values['-REPORT_PREVIEW-']
        if report:
            save_as_csv(inventory)
        else:
            sg.popup_error('Please generate a report first', font=FONT_NORMAL)

def update_product_fields(window, product):
    window['-PRODUCT-'].update(product['Product Code'])
    window['-SUPPLIER_PRODUCT-'].update(product['Supplier Product Code'])
    window['-DEPARTMENT-'].update(product['Department'])

def update_inventory_table(window, inventory):
    window['-INVENTORY_TABLE-'].update([[item['Department'], item['Product Code'], item['Product Description'], item['Quantity'], item['Unit'], item['Status']] for item in inventory])

def show_product_details(product, auth_system):
    # Get the current manager info
    user_info = auth_system.get_current_user_info()
    manager_info = f"Viewed by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Viewed by: N/A"
    
    layout = [
        [sg.Text(f"Product Details: {product['Product Description']}", font=FONT_SUBHEADER)],
        [sg.Text(f"Product Code: {product['Product Code']}")],
        [sg.Text(f"Supplier: {product['Supplier']}")],
        [sg.Text(f"Batch/Lot: {product['Batch/Lot']}")],
        [sg.Text(f"Quantity: {product['Quantity']} {product['Unit']}")],
        [sg.Text(f"Status: {product['Status']}")],
        [sg.Text(f"Current Location: {product['Current Location']}")],
        [sg.Text("Handling History:")],
        [sg.Multiline(product['Handling History'], size=(50, 5), disabled=True)],
        [sg.Text("Temperature Log:")],
        [sg.Multiline('\n'.join(product['Temperature Log']), size=(50, 5), disabled=True)],
        [sg.Text(f"Processed By: {product.get('Processed By', 'N/A')}")],
        [sg.Text("─" * 50)],  # Divider line
        [sg.Text(manager_info, font=('Helvetica', 10, 'italic'))],  # Manager info
        [sg.Button('Close')]
    ]
    window = sg.Window('Product Details', layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
    window.close()

def generate_report(inventory, report_type, start_date, end_date, auth_system):
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    if report_type == 'Traceability':
        return generate_traceability_report(inventory, start_date, end_date, auth_system)
    elif report_type == 'Inventory Summary':
        return generate_inventory_summary(inventory, start_date, end_date)
    elif report_type == 'Temperature Log':
        return generate_temperature_log(inventory, start_date, end_date)
    else:
        return "Invalid report type"

def generate_traceability_report(inventory, start_date, end_date, auth_system):
    user_info = auth_system.get_current_user_info()
    manager_info = f"Report Generated by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Report Generated by: N/A"
    
    report = f"Traceability Report\n"
    report += f"{manager_info}\n"
    report += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for item in inventory:
        delivery_date = datetime.strptime(item['Delivery Date'], '%Y-%m-%d %H:%M:%S')
        if start_date <= delivery_date <= end_date:
            report += f"Product: {item['Product Description']}\n"
            report += f"Product Code: {item['Product Code']}\n"
            report += f"Supplier: {item['Supplier']}\n"
            report += f"Batch/Lot: {item['Batch/Lot']}\n"
            report += f"Delivery Date: {item['Delivery Date']}\n"
            report += f"Current Status: {item['Status']}\n"
            report += f"Current Location: {item['Current Location']}\n"
            report += f"Processed By: {item.get('Processed By', 'N/A')}\n\n"
    return report

def generate_inventory_summary(inventory, start_date, end_date, auth_system):
    user_info = auth_system.get_current_user_info()
    manager_info = f"Report Generated by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Report Generated by: N/A"
    
    summary = {}
    for item in inventory:
        delivery_date = datetime.strptime(item['Delivery Date'], '%Y-%m-%d %H:%M:%S')
        if start_date <= delivery_date <= end_date:
            dept = item['Department']
            if dept not in summary:
                summary[dept] = {'total_items': 0, 'total_quantity': 0}
            summary[dept]['total_items'] += 1
            summary[dept]['total_quantity'] += float(item['Quantity'])
    
    report = f"Inventory Summary Report\n"
    report += f"{manager_info}\n"
    report += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for dept, data in summary.items():
        report += f"Department: {dept}\n"
        report += f"Total Items: {data['total_items']}\n"
        report += f"Total Quantity: {data['total_quantity']}\n\n"
    return report

def generate_temperature_log(inventory, start_date, end_date, auth_system):
    user_info = auth_system.get_current_user_info()
    manager_info = f"Report Generated by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Report Generated by: N/A"
    
    report = f"Temperature Log Report\n"
    report += f"{manager_info}\n"
    report += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for item in inventory:
        for log in item['Temperature Log']:
            log_date = datetime.strptime(log.split(':')[0], '%Y-%m-%d %H:%M:%S')
            if start_date <= log_date <= end_date:
                report += f"Product: {item['Product Description']}\n"
                report += f"Log: {log}\n\n"
    return report

def show_login_window(auth_system):
    layout = [
        [sg.Text('Username:', size=(15, 1)), sg.Input(key='-USERNAME-')],
        [sg.Text('Password:', size=(15, 1)), sg.Input(key='-PASSWORD-', password_char='*')],
        [sg.Button('Login', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Exit', button_color=(COLORS['text'], COLORS['secondary']))]
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
                sg.popup_error('Login failed. Please try again.')
    
        window.close()
        return False

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
        [sg.Button('Submit', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Cancel', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['secondary']))]
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

def generate_and_show_barcode(item):
    combined_batch = f"{item['Batch/Lot']}-{item['Supplier Batch No']}"
    barcode_image = generate_barcode(combined_batch)
    
    bio = io.BytesIO()
    barcode_image.save(bio, format="PNG")
    barcode_data = bio.getvalue()
    
    layout = [
        [sg.Text(item['Product Description'], font=FONT_NORMAL)],
        [sg.Image(data=barcode_data, key='-IMAGE-')],
        [sg.Button('Save Barcode', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Close', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    window = sg.Window('Barcode', layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
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

def save_as_pdf(report):
    filename = sg.popup_get_file('Save PDF as', save_as=True, file_types=(("PDF Files", "*.pdf"),))
    if filename:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, report)
        pdf.output(filename)
        sg.popup(f"Report saved as {filename}")

def save_as_csv(inventory):
    filename = sg.popup_get_file('Save CSV as', save_as=True, file_types=(("CSV Files", "*.csv"),))
    if filename:
        with open(filename, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=inventory[0].keys())
            writer.writeheader()
            writer.writerows(inventory)
        sg.popup(f"Report saved as {filename}")

if __name__ == "__main__":
    file_paths = ['Butchery reports Big G.csv', 'Bakery Big G.csv', 'HMR Big G.csv']
    df = load_data(file_paths)
    create_gui(df)