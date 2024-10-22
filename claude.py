def show_role_selection():
    layout = [
        [sg.Text('Select Your Role', font=FONT_HEADER, justification='center')],
        [sg.Radio('Delivery Manager', 'ROLE', key='-DELIVERY-', default=True)],
        [sg.Radio('Department Manager', 'ROLE', key='-DEPARTMENT-')],
        [sg.Button('Continue', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Exit', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    window = sg.Window('Role Selection', layout, finalize=True)
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            window.close()
            return None
        if event == 'Continue':
            role = 'Delivery' if values['-DELIVERY-'] else 'Department'
            window.close()
            return role

def show_login_window(auth_system, required_role):
    layout = [
        [sg.Text(f'{required_role} Login', font=FONT_SUBHEADER)],
        [sg.Text('Username:', size=(15, 1)), sg.Input(key='-USERNAME-')],
        [sg.Text('Password:', size=(15, 1)), sg.Input(key='-PASSWORD-', password_char='*')],
        [sg.Button('Login', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Back', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    window = sg.Window('Login', layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Back'):
            window.close()
            return False, None
        if event == 'Login':
            username = values['-USERNAME-']
            password = values['-PASSWORD-']
            if auth_system.login(username, password):
                user_info = auth_system.get_current_user_info()
                if user_info['department'] == required_role:
                    window.close()
                    return True, user_info
                else:
                    auth_system.logout()
                    sg.popup_error(f'You are not authorized as a {required_role} user.')
            else:
                sg.popup_error('Login failed. Please try again.')
    
    window.close()
    return False, None

def create_delivery_manager_window(df, inventory):
    layout = [
        [sg.Text('Delivery Manager Dashboard', font=FONT_HEADER, justification='center')],
        [sg.Frame('Product Reception', [
            [sg.Text('Product Description:', size=(15, 1)),
             sg.Combo(sorted(df['Product Description'].unique()), key='-PRODUCT_DESC-', size=(40, 1), enable_events=True)],
            [sg.Text('Department:', size=(15, 1)),
             sg.Input(key='-DEPARTMENT-', readonly=True)],
            [sg.Text('Product Code:', size=(15, 1)),
             sg.Input(key='-PRODUCT_CODE-', readonly=True)],
            [sg.Text('Quantity:', size=(15, 1)),
             sg.Input(key='-QUANTITY-'), 
             sg.Combo(['unit', 'kg'], default_value='unit', key='-UNIT-')],
            [sg.Text('Batch Number:', size=(15, 1)),
             sg.Input(key='-BATCH-')],
            [sg.Button('Receive Product', button_color=(COLORS['text'], COLORS['primary']))],
        ])],
        [sg.Frame('Pending Deliveries', [
            [sg.Table(
                values=[],
                headings=['Department', 'Product', 'Quantity', 'Status'],
                auto_size_columns=True,
                num_rows=10,
                key='-DELIVERY_TABLE-'
            )]
        ])],
        [sg.Button('Logout', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    return sg.Window('Delivery Manager', layout, finalize=True, resizable=True)

def create_department_manager_window(department, inventory):
    layout = [
        [sg.Text(f'{department} Manager Dashboard', font=FONT_HEADER, justification='center')],
        [sg.Frame('Department Inventory', [
            [sg.Table(
                values=[],
                headings=['Product', 'Quantity', 'Status', 'Batch'],
                auto_size_columns=True,
                num_rows=10,
                key='-INVENTORY_TABLE-',
                enable_events=True
            )]
        ])],
        [sg.Button('Process Selected', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('View Details', button_color=(COLORS['text'], COLORS['secondary'])),
         sg.Button('Logout', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    return sg.Window(f'{department} Manager', layout, finalize=True, resizable=True)

def update_department_inventory(window, inventory, department):
    dept_inventory = [
        [item['Product Description'], item['Quantity'], item['Status'], item['Batch/Lot']]
        for item in inventory 
        if item['Department'] == department and item['Status'] != 'Processed'
    ]
    window['-INVENTORY_TABLE-'].update(dept_inventory)

def update_delivery_table(window, inventory):
    pending_deliveries = [
        [item['Department'], item['Product Description'], item['Quantity'], item['Status']]
        for item in inventory 
        if item['Status'] == 'Delivered'
    ]
    window['-DELIVERY_TABLE-'].update(pending_deliveries)

def main():
    auth_system = AuthSystem()
    # Add sample users
    auth_system.add_user("john_delivery", "pass123", "Delivery", "Manager")
    auth_system.add_user("mary_butchery", "pass456", "Butchery", "Manager")
    auth_system.add_user("peter_bakery", "pass789", "Bakery", "Manager")
    auth_system.add_user("sarah_hmr", "pass321", "HMR", "Manager")
    
    inventory = []
    file_paths = ['Butchery reports Big G.csv', 'Bakery Big G.csv', 'HMR Big G.csv']
    df = load_data(file_paths)
    
    while True:
        role = show_role_selection()
        if not role:
            break
            
        success, user_info = show_login_window(auth_system, role)
        if not success:
            continue
            
        if role == 'Delivery':
            window = create_delivery_manager_window(df, inventory)
            while True:
                event, values = window.read()
                if event in (sg.WIN_CLOSED, 'Logout'):
                    break
                    
                if event == '-PRODUCT_DESC-':
                    if values['-PRODUCT_DESC-']:
                        product = df[df['Product Description'] == values['-PRODUCT_DESC-']].iloc[0]
                        window['-DEPARTMENT-'].update(product['Department'])
                        window['-PRODUCT_CODE-'].update(product['Product Code'])
                        
                if event == 'Receive Product':
                    # Add delivery logic here
                    product = deliver_product(
                        df,
                        values['-PRODUCT_CODE-'],
                        values['-QUANTITY-'],
                        values['-UNIT-'],
                        values['-BATCH-'],
                        datetime.now().strftime('%Y-%m-%d'),
                        auth_system
                    )
                    inventory.append(product)
                    update_delivery_table(window, inventory)
                    sg.popup('Product received successfully')
                    
            window.close()
        else:
            window = create_department_manager_window(user_info['department'], inventory)
            while True:
                event, values = window.read()
                if event in (sg.WIN_CLOSED, 'Logout'):
                    break
                    
                if event == 'Process Selected':
                    selected_rows = values['-INVENTORY_TABLE-']
                    if selected_rows:
                        for idx in selected_rows:
                            product = inventory[idx]
                            if product['Department'] == user_info['department']:
                                processed_product = process_product(product, auth_system)
                                inventory[idx] = processed_product
                        update_department_inventory(window, inventory, user_info['department'])
                        sg.popup('Products processed successfully')
                    else:
                        sg.popup_error('Please select products to process')
                        
                if event == 'View Details':
                    selected_rows = values['-INVENTORY_TABLE-']
                    if selected_rows:
                        show_product_details(inventory[selected_rows[0]], auth_system)
                        
                update_department_inventory(window, inventory, user_info['department'])
                
            window.close()
            
        auth_system.logout()

if __name__ == "__main__":
    main()