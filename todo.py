import json
import os

TASKS_FILE = "todo.json"

def load_tasks():
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, "r") as f:
        return json.load(f)

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def add_task(tasks, description):
    tasks.append({"description": description, "completed": False})
    save_tasks(tasks)
    print(f"Task added: {description}")

def view_tasks(tasks):
    if not tasks:
        print("No tasks found.")
        return
    for idx, task in enumerate(tasks, 1):
        status = "✓" if task["completed"] else "✗"
        print(f"{idx}. [{status}] {task['description']}")

def mark_complete(tasks, index):
    if 0 <= index < len(tasks):
        tasks[index]["completed"] = True
        save_tasks(tasks)
        print(f"Task marked as complete: {tasks[index]['description']}")
    else:
        print("Invalid task number.")

def delete_task(tasks, index):
    if 0 <= index < len(tasks):
        removed = tasks.pop(index)
        save_tasks(tasks)
        print(f"Deleted task: {removed['description']}")
    else:
        print("Invalid task number.")

def main():
    tasks = load_tasks()
    while True:
        print("\nTODO Application")
        print("1. Add task")
        print("2. View all tasks")
        print("3. Mark task as complete")
        print("4. Delete task")
        print("5. Exit")
        choice = input("Choose an option: ")
        if choice == "1":
            desc = input("Enter task description: ")
            add_task(tasks, desc)
        elif choice == "2":
            view_tasks(tasks)
        elif choice == "3":
            view_tasks(tasks)
            idx = int(input("Enter task number to mark complete: ")) - 1
            mark_complete(tasks, idx)
        elif choice == "4":
            view_tasks(tasks)
            idx = int(input("Enter task number to delete: ")) - 1
            delete_task(tasks, idx)
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
