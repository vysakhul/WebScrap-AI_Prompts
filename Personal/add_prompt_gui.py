import os
import csv
from datetime import datetime
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

# --- Configuration ---
BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR / "personal_data.csv"
IMAGE_DIR = BASE_DIR / "images"

# Standardized fields to match the Meigen schema exactly
CSV_FIELDS = [
    "id",
    "title",
    "prompt",
    "category_tag",
    "model",
    "image_url",
    "local_path",
    "author_name"
]

# Configure CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AddPromptApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Prompt Vault - Personal Add")
        self.geometry("600x550")
        self.resizable(False, False)

        # Main Frame
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # Header
        self.header_label = ctk.CTkLabel(self.main_frame, text="Add Personal Prompt",
                                         font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.grid(row=0, column=0, columnspan=2, pady=(20, 20))

        # Image Selection
        self.img_path_var = ctk.StringVar()
        self.img_button = ctk.CTkButton(self.main_frame, text="Browse Image", command=self.browse_image)
        self.img_button.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="w")

        self.img_label = ctk.CTkLabel(self.main_frame, textvariable=self.img_path_var, text_color="gray", width=350,
                                      anchor="w")
        self.img_label.grid(row=1, column=1, padx=(0, 20), pady=10, sticky="w")

        # Title
        self.title_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Title (Optional)", width=400)
        self.title_entry.grid(row=2, column=0, columnspan=2, padx=20, pady=10)

        # Prompt
        self.prompt_textbox = ctk.CTkTextbox(self.main_frame, width=400, height=120)
        self.prompt_textbox.insert("0.0", "Enter your prompt here...")
        self.prompt_textbox.bind("<FocusIn>", self.clear_placeholder)
        self.prompt_textbox.grid(row=3, column=0, columnspan=2, padx=20, pady=10)

        # Category & Model
        self.category_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Category / Tag (e.g., Character Design)",
                                           width=400)
        self.category_entry.grid(row=4, column=0, columnspan=2, padx=20, pady=10)

        self.model_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Model (e.g., Midjourney v6)", width=400)
        self.model_entry.grid(row=5, column=0, columnspan=2, padx=20, pady=10)

        # Save Button
        self.save_button = ctk.CTkButton(self.main_frame, text="Save to Vault", font=ctk.CTkFont(weight="bold"),
                                         command=self.save_prompt)
        self.save_button.grid(row=6, column=0, columnspan=2, pady=(30, 20))

        # Ensure database and folders exist
        self.init_database()

    def clear_placeholder(self, event):
        if self.prompt_textbox.get("0.0", "end-1c") == "Enter your prompt here...":
            self.prompt_textbox.delete("0.0", "end")

    def browse_image(self):
        file_path = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp")]
        )
        if file_path:
            self.img_path_var.set(file_path)

    def init_database(self):
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        if not CSV_FILE.exists():
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()

    def save_prompt(self):
        src_image_path = self.img_path_var.get()
        prompt_text = self.prompt_textbox.get("0.0", "end-1c").strip()
        category = self.category_entry.get().strip()
        model = self.model_entry.get().strip()
        title = self.title_entry.get().strip()

        # Validations
        if not src_image_path or src_image_path == "No file selected":
            messagebox.showwarning("Missing Data", "Please select an image file.")
            return
        if not prompt_text or prompt_text == "Enter your prompt here...":
            messagebox.showwarning("Missing Data", "Please enter the prompt.")
            return
        if not category:
            messagebox.showwarning("Missing Data", "Please enter a Category.")
            return

        # Generate Unique ID using datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = f"personal_{timestamp}"

        # We force .jpg here because we are compressing everything to JPEG
        new_img_name = f"{unique_id}.jpg"
        dest_image_path = IMAGE_DIR / new_img_name

        try:
            # 1. Process and Compress Image
            with Image.open(src_image_path) as img:
                # Convert to RGB if it is a PNG with transparency (prevents JPEG crash)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Set a sensible max width for the gallery (1024px)
                max_width = 1024
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = int(img.height * ratio)
                    # Resize while maintaining aspect ratio
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                # Save as JPG with optimization
                img.save(dest_image_path, "JPEG", optimize=True, quality=85)

            # 2. Append to CSV
            row = {
                "id": unique_id,
                "title": title if title else "My Prompt",
                "prompt": prompt_text,
                "category_tag": category,
                "model": model if model else "Unknown",
                "image_url": "",
                "local_path": f"images/{new_img_name}",
                "author_name": "Personal"
            }

            with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerow(row)

            # Success & Reset UI
            messagebox.showinfo("Success", "Prompt successfully saved to your Personal Vault!")
            self.img_path_var.set("")
            self.title_entry.delete(0, "end")
            self.prompt_textbox.delete("0.0", "end")
            self.prompt_textbox.insert("0.0", "Enter your prompt here...")
            self.category_entry.delete(0, "end")
            self.model_entry.delete(0, "end")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving:\n{str(e)}")


if __name__ == "__main__":
    app = AddPromptApp()
    app.mainloop()