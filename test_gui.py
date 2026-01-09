import tkinter as tk
from tkinter import messagebox
import sys

def on_click():
    messagebox.showinfo("성공", "Tkinter가 정상적으로 작동합니다!\nPython 버전: " + sys.version)

def main():
    try:
        root = tk.Tk()
        root.title("Mac Tkinter Test")
        root.geometry("300x200")

        label = tk.Label(root, text="이 창이 보이면 성공입니다.", pady=20)
        label.pack()

        btn = tk.Button(root, text="클릭해보세요", command=on_click)
        btn.pack()

        print("GUI 창을 띄웁니다...")
        root.mainloop()
        print("GUI 창이 닫혔습니다.")
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    main()

