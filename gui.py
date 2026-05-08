import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Import constants from crypto_utils for path displays
try:
    from crypto_utils import TYPELESS_DIR, IS_WIN
except ImportError:
    TYPELESS_DIR = "未知"
    IS_WIN = False

class TypelessGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Typeless 重置与迁移工具 v3.0")
        self.root.geometry("600x450")
        self.root.resizable(False, False)

        self.setup_ui()

    def setup_ui(self):
        # Header
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(fill="x")
        
        ttk.Label(
            header_frame, 
            text="Typeless 设备重置与数据迁移工具", 
            font=("Microsoft YaHei", 16, "bold")
        ).pack()
        
        ttk.Label(
            header_frame, 
            text=f"检测到数据路径: {TYPELESS_DIR}",
            font=("Microsoft YaHei", 9),
            foreground="gray"
        ).pack()

        # Main Action Area
        action_frame = ttk.LabelFrame(self.root, text="操作流程", padding="20")
        action_frame.pack(padx=20, pady=10, fill="both", expand=True)

        # Step 1: Export
        step1_frame = ttk.Frame(action_frame)
        step1_frame.pack(fill="x", pady=5)
        ttk.Label(step1_frame, text="步骤 1: 备份当前账号数据", width=35).pack(side="left")
        ttk.Button(step1_frame, text="开始备份", command=self.run_export).pack(side="right")

        # Step 2: Reset
        step2_frame = ttk.Frame(action_frame)
        step2_frame.pack(fill="x", pady=5)
        ttk.Label(step2_frame, text="步骤 2: 重置设备 ID (解除登录限制)", width=35).pack(side="left")
        ttk.Button(step2_frame, text="重置设备", command=self.run_reset).pack(side="right")

        # Step 3: Import
        step3_frame = ttk.Frame(action_frame)
        step3_frame.pack(fill="x", pady=5)
        ttk.Label(step3_frame, text="步骤 3: 恢复数据到新账号", width=35).pack(side="left")
        ttk.Button(step3_frame, text="恢复数据", command=self.run_import).pack(side="right")

        # Console/Log Area
        log_frame = ttk.LabelFrame(self.root, text="运行日志", padding="5")
        log_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Use a scrolling text area for logs
        self.log_text = tk.Text(log_frame, height=8, state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"> {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def run_command(self, script_name, *args):
        try:
            # Direct execution using current python interpreter to avoid uv environment issues
            # Since gui.py is already running inside 'uv run', sys.executable is the venv python.
            cmd = [sys.executable, script_name] + list(args)
            
            # Use subprocess.PIPE to capture output line by line
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                universal_newlines=True
            )
            
            if process.stdout:
                for line in process.stdout:
                    self.log(line.strip())
            
            process.wait()
            return process.returncode == 0
        except Exception as e:
            self.log(f"错误: {str(e)}")
            return False

    def run_export(self):
        if messagebox.askyesno("确认", "是否立即备份所有词典与历史记录？"):
            self.log("正在开始备份...")
            if self.run_command("export.py"):
                messagebox.showinfo("成功", "备份完成！请检查当前目录下的 backup_ 文件夹。")
            else:
                messagebox.showerror("错误", "备份失败，请查看日志详情。")

    def run_reset(self):
        if messagebox.askyesno("警告", "这将强制关闭 Typeless 并重置设备 ID。是否继续？"):
            self.log("正在重置设备...")
            if self.run_command("reset.py"):
                messagebox.showinfo("成功", "设备重置成功！请现在启动 Typeless 并登录【新账号】。")
            else:
                messagebox.showerror("错误", "重置失败，请查看日志详情。")

    def run_import(self):
        backup_dir = filedialog.askdirectory(title="选择备份目录")
        if not backup_dir:
            return
            
        if messagebox.askyesno("确认", f"是否将数据从 {os.path.basename(backup_dir)} 恢复到当前登录的账号？"):
            self.log(f"正在从 {backup_dir} 恢复数据...")
            if self.run_command("import.py", backup_dir):
                messagebox.showinfo("成功", "数据恢复成功！")
            else:
                messagebox.showerror("错误", "恢复失败，请查看日志详情。")

if __name__ == "__main__":
    root = tk.Tk()
    app = TypelessGUI(root)
    root.mainloop()
