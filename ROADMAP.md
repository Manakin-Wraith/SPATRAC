**Roadmap (High-Level Phases):**

1. **Database Setup and Data Loading:**  Establish the database structure and populate it with initial product and recipe data.
2. **Core UI Development:** Create the main application windows (Login, Receiving, Department Windows).
3. **User Authentication and Authorization:** Implement login functionality and role-based access control.
4. **Receiving Workflow:**  Develop the product receiving process in the Receiving Window.
5. **Department Workflow:**  Implement product processing and basic recipe management within the Department Windows.
6. **Testing and Refinement:** Thoroughly test and refine the application based on feedback.
7. **Deployment:** Prepare and deploy the MVP to your target environment.

**Backlog (Detailed Tasks):**

**Sprint 1: Database and Basic UI**

* **Task 1:** Create database schema in SQLite (Tables: Users, Departments, Suppliers, Products, Inventory, HandlingHistory, TemperatureLogs, FinalProducts, FinalProductIngredients).
* **Task 2:** Write functions to load product data from CSV into the Products table.
* **Task 3:** Write functions to load recipe data from CSV into FinalProducts and FinalProductIngredients tables.
* **Task 4:** Create the Login window UI (username, password, login/exit buttons).
* **Task 5:** Create basic UI layouts for the Receiving window and one Department window (e.g., Butchery).  Don't implement functionality yet; focus on visual design.

**Sprint 2: Authentication and Receiving**

* **Task 6:** Implement user authentication in the login window (check against the Users table).
* **Task 7:** Implement role-based redirection after login (Delivery Manager -> Receiving Window, Department Manager -> Department Window).
* **Task 8:** Implement the "Receive Product" functionality in the Receiving Window (update the Inventory table).
* **Task 9:** Add basic input validation for receiving product details (e.g., check for numeric quantities).

**Sprint 3: Department Workflow and Recipe Linking**

* **Task 10:** Display department-specific inventory in the Department Window (fetch data from the Inventory table).
* **Task 11:** Implement the "Process Selected" functionality (update Inventory status and location).
* **Task 12:**  Implement UI for linking processed ingredients to final products (dropdown for final products, input for quantity used).
* **Task 13:** Implement basic recipe management: display ingredients for a selected final product.

**Sprint 4:  Inventory Consumption and Testing**

* **Task 14:** Implement inventory consumption: deduct ingredients from inventory when linked to a final product.
* **Task 15:** Thoroughly test all implemented features with different user roles and scenarios.
* **Task 16:**  Fix bugs and refine the UI/UX based on testing feedback.

**Sprint 5: Deployment and Documentation**

* **Task 17:**  Set up the deployment environment (shared database or file share).
* **Task 18:** Deploy the application to the target devices.
* **Task 19:** Create basic user documentation (how to log in, receive products, process products, etc.).

**Prioritization:**

The backlog is ordered by priority.  Focus on completing the tasks in each sprint before moving on to the next.  This iterative approach allows for flexibility and incorporates feedback early in the process.

**Technical Considerations:**

* Use parameterized SQL queries to prevent SQL injection vulnerabilities.
* Handle potential database errors gracefully.
* Consider using a more robust database (e.g., PostgreSQL) if scalability or concurrent access becomes an issue.

This roadmap and backlog should provide a clear path for building your SPATRAC MVP.  Remember to adapt and adjust based on your specific needs and priorities as you progress through the development process.  This breakdown should also help you communicate progress and tasks with any stakeholders.
