import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, filedialog
import threading
import time
import subprocess
import pyautogui
from pynput import keyboard
from screen_capture_tool import ScreenCaptureTool
from PIL import Image, ImageTk
import os
import json
import shutil

class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("블루스택 터치 매크로 Pro")
        self.root.geometry("1100x750") # 쿨타임 컬럼 추가로 너비 확장
        
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.macro_running = False
        self.macro_thread = None
        self.listener = None
        
        # action 구조: {name, image_path, delay(후딜), cooldown(쿨타임), last_run(마지막실행시간)}
        self.action_list = [] 
        self.selected_app_name = tk.StringVar()
        self.execution_mode = tk.StringVar(value="sequential") 
        
        self.preview_image_ref = None 

        self.screen_capture_tool = ScreenCaptureTool(self.root, self._add_action_from_capture)
        
        pyautogui.FAILSAFE = False 

        self._create_widgets()
        self._start_keyboard_listener()
        self._load_profile_list()

    def _add_action_from_capture(self, name, image_path, delay):
        # 캡처 툴에서는 쿨타임 0으로 기본 설정 (나중에 편집 가능)
        self.action_list.append({
            "name": name,
            "image_path": image_path,
            "delay": delay,
            "cooldown": 0.0,
            "last_run": 0.0
        })
        self._refresh_action_list()
        self._update_ui_state()

    def _start_keyboard_listener(self):
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()

    def _on_key_press(self, key):
        if key == keyboard.Key.esc:
            if self.macro_running:
                self._log("!!! ESC 키 눌림: 매크로 긴급 정지 !!!")
                self.stop_macro()

    def _get_running_apps(self):
        try:
            cmd = """osascript -e 'tell application "System Events" to get name of every process whose background only is false'"""
            result = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
            apps = [app.strip() for app in result.split(',')]
            apps.sort()
            return apps
        except Exception as e:
            return []

    def _activate_app(self, app_name):
        try:
            cmd = f"""osascript -e 'tell application "{app_name}" to activate'"""
            subprocess.run(cmd, shell=True, check=True)
        except Exception:
            try:
                subprocess.run(["open", "-a", app_name], check=True)
            except Exception as e:
                print(f"앱 활성화 실패 ({app_name}): {e}")
        time.sleep(1.0)

    # --- UI 구성 ---
    def _create_widgets(self):
        # 1. 상단 패널
        top_frame = tk.LabelFrame(self.root, text="기본 설정", padx=10, pady=5)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(top_frame, text="대상 앱:").pack(side=tk.LEFT)
        self.app_combo = ttk.Combobox(top_frame, textvariable=self.selected_app_name, width=20)
        self.app_combo['values'] = self._get_running_apps()
        if self.app_combo['values']: self.app_combo.current(0)
        self.app_combo.pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="↻", width=2, command=self._refresh_app_list).pack(side=tk.LEFT)

        tk.Label(top_frame, text="  |  실행 모드:").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(top_frame, text="순차 실행 (1->2->3)", variable=self.execution_mode, value="sequential").pack(side=tk.LEFT)
        tk.Radiobutton(top_frame, text="발견 즉시 실행 (무작위)", variable=self.execution_mode, value="any").pack(side=tk.LEFT)

        # 2. 메인 컨텐츠
        content_frame = tk.Frame(self.root)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 좌측: 동작 리스트 (컬럼 추가: Cooldown)
        left_frame = tk.LabelFrame(content_frame, text="동작 리스트", padx=5, pady=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(left_frame, columns=("Order", "Name", "Delay", "Cooldown"), show="headings")
        self.tree.heading("Order", text="No.")
        self.tree.heading("Name", text="이름")
        self.tree.heading("Delay", text="대기(후)")
        self.tree.heading("Cooldown", text="쿨타임(초)")
        
        self.tree.column("Order", width=40, anchor=tk.CENTER)
        self.tree.column("Name", width=180)
        self.tree.column("Delay", width=70, anchor=tk.CENTER)
        self.tree.column("Cooldown", width=70, anchor=tk.CENTER)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_list_select)
        # 더블 클릭 시 편집 기능 연결
        self.tree.bind("<Double-1>", lambda e: self._edit_action())

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 우측: 컨트롤 패널
        right_frame = tk.Frame(content_frame, padx=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # 이미지 프리뷰
        preview_labelframe = tk.LabelFrame(right_frame, text="이미지 미리보기", width=250, height=180)
        preview_labelframe.pack(fill=tk.X, pady=5)
        preview_labelframe.pack_propagate(False)

        self.preview_label = tk.Label(preview_labelframe, text="선택된 이미지 없음")
        self.preview_label.pack(expand=True)

        # 편집 버튼들
        edit_frame = tk.LabelFrame(right_frame, text="편집", padx=5, pady=5)
        edit_frame.pack(fill=tk.X, pady=5)

        self.add_file_btn = tk.Button(edit_frame, text="📂 파일에서 추가", command=self._add_from_file_action)
        self.add_file_btn.pack(fill=tk.X, pady=2)

        self.add_btn = tk.Button(edit_frame, text="➕ 이미지 추가 (캡처)", command=self._add_image_action, bg="#e1f5fe")
        self.add_btn.pack(fill=tk.X, pady=2)
        
        # [신규] 선택 편집 버튼
        self.edit_btn = tk.Button(edit_frame, text="✏️ 선택 항목 편집 (시간)", command=self._edit_action)
        self.edit_btn.pack(fill=tk.X, pady=2)
        
        self.del_btn = tk.Button(edit_frame, text="➖ 선택 삭제", command=self._delete_action)
        self.del_btn.pack(fill=tk.X, pady=2)

        tk.Frame(edit_frame, height=5).pack()

        self.up_btn = tk.Button(edit_frame, text="⬆️ 위로 이동", command=self._move_up)
        self.up_btn.pack(fill=tk.X, pady=2)
        
        self.down_btn = tk.Button(edit_frame, text="⬇️ 아래로 이동", command=self._move_down)
        self.down_btn.pack(fill=tk.X, pady=2)

        # 3. 하단 패널
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 프로필 관리
        profile_frame = tk.LabelFrame(bottom_frame, text="프로필 관리", padx=5, pady=5)
        profile_frame.pack(fill=tk.X, pady=5)

        tk.Label(profile_frame, text="현재 프로필:").pack(side=tk.LEFT)
        self.profile_combo = ttk.Combobox(profile_frame, width=20, state="readonly")
        self.profile_combo.pack(side=tk.LEFT, padx=5)
        
        tk.Button(profile_frame, text="불러오기", command=self._load_selected_profile).pack(side=tk.LEFT, padx=2)
        tk.Button(profile_frame, text="새 프로필 저장", command=self._save_profile_as).pack(side=tk.LEFT, padx=2)
        tk.Button(profile_frame, text="현재 상태 저장", command=self._save_current_profile).pack(side=tk.LEFT, padx=2)

        # 실행 버튼
        run_frame = tk.Frame(bottom_frame, pady=5)
        run_frame.pack(fill=tk.X)
        
        self.start_btn = tk.Button(run_frame, text="▶ 매크로 시작", command=self.start_macro, font=("Arial", 14, "bold"), bg="#c8e6c9", height=2)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.stop_btn = tk.Button(run_frame, text="⏹ 정지 (ESC)", command=self.stop_macro, font=("Arial", 14, "bold"), bg="#ffcdd2", height=2, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 로그
        log_frame = tk.LabelFrame(bottom_frame, text="로그", padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=8, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._update_ui_state()

    # --- 기능 구현 ---
    def _refresh_app_list(self):
        self.app_combo['values'] = self._get_running_apps()
        self._log("앱 목록 갱신 완료.")

    def _resolve_image_path(self, path):
        if os.path.exists(path): return path
        new_path = os.path.join(self.base_dir, path)
        if os.path.exists(new_path): return new_path
        if "images" in path:
            filename = os.path.basename(path)
            fixed_path = os.path.join(self.base_dir, "images", filename)
            if os.path.exists(fixed_path): return fixed_path
        return path

    def _on_list_select(self, event):
        selected = self.tree.selection()
        if not selected:
            self.preview_label.config(image='', text="선택된 이미지 없음")
            return
        
        item_idx = self.tree.index(selected[0])
        action = self.action_list[item_idx]
        image_path = self._resolve_image_path(action['image_path'])

        try:
            img = Image.open(image_path)
            img.thumbnail((230, 160))
            self.preview_image_ref = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image_ref, text="")
        except Exception as e:
            self.preview_label.config(image='', text=f"이미지 로드 실패\n{os.path.basename(image_path)}")

    def _add_image_action(self):
        try:
            target_app = self.selected_app_name.get()
            if target_app: self._activate_app(target_app)
            self.screen_capture_tool.capture_and_select()
        except Exception as e:
            self._log(f"이미지 추가 에러: {e}")

    def _add_from_file_action(self):
        file_path = filedialog.askopenfilename(title="이미지 파일 선택", filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
        if not file_path: return

        default_name = os.path.splitext(os.path.basename(file_path))[0]
        name = simpledialog.askstring("동작 추가", "이름 입력:", initialvalue=default_name)
        if not name: return
        
        images_dir = os.path.join(self.base_dir, "images")
        if not os.path.exists(images_dir): os.makedirs(images_dir)
            
        ext = os.path.splitext(file_path)[1]
        new_filename = f"{name}_{int(time.time())}{ext}"
        target_path = os.path.join(images_dir, new_filename)
        
        try:
            shutil.copy(file_path, target_path)
            self.action_list.append({
                "name": name, "image_path": target_path, "delay": 1.0, "cooldown": 0.0, "last_run": 0.0
            })
            self._refresh_action_list()
            self._update_ui_state()
            self._log(f"파일 추가 완료: {name}")
        except Exception as e:
            messagebox.showerror("에러", f"추가 실패: {e}")

    # [신규] 동작 편집 기능
    def _edit_action(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("경고", "편집할 항목을 선택해주세요.")
            return

        idx = self.tree.index(selected[0])
        action = self.action_list[idx]

        # 1. 이름 편집
        new_name = simpledialog.askstring("편집", "동작 이름:", initialvalue=action['name'])
        if new_name is None: return # 취소
        
        # 2. 대기 시간(후딜) 편집
        new_delay_str = simpledialog.askstring("편집", "동작 후 대기 시간 (초):", initialvalue=str(action['delay']))
        if new_delay_str is None: return
        
        # 3. 쿨타임 편집
        new_cooldown_str = simpledialog.askstring("편집", "스킬 쿨타임 (초)\n(이 시간 동안은 재클릭 안 함):", initialvalue=str(action.get('cooldown', 0.0)))
        if new_cooldown_str is None: return

        try:
            action['name'] = new_name
            action['delay'] = float(new_delay_str)
            action['cooldown'] = float(new_cooldown_str)
            self._refresh_action_list()
            self._log(f"'{new_name}' 수정 완료.")
        except ValueError:
            messagebox.showerror("에러", "숫자를 정확히 입력해주세요.")

    def _delete_action(self):
        selected = self.tree.selection()
        if not selected: return
        if messagebox.askyesno("삭제", "선택 항목을 삭제하시겠습니까?"):
            idx = self.tree.index(selected[0])
            del self.action_list[idx]
            self._refresh_action_list()

    def _move_up(self):
        selected = self.tree.selection()
        if not selected: return
        idx = self.tree.index(selected[0])
        if idx > 0:
            self.action_list[idx], self.action_list[idx-1] = self.action_list[idx-1], self.action_list[idx]
            self._refresh_action_list()
            self.tree.selection_set(self.tree.get_children()[idx-1])

    def _move_down(self):
        selected = self.tree.selection()
        if not selected: return
        idx = self.tree.index(selected[0])
        if idx < len(self.action_list) - 1:
            self.action_list[idx], self.action_list[idx+1] = self.action_list[idx+1], self.action_list[idx]
            self._refresh_action_list()
            self.tree.selection_set(self.tree.get_children()[idx+1])

    def _refresh_action_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, action in enumerate(self.action_list):
            cooldown = action.get('cooldown', 0.0)
            self.tree.insert("", tk.END, values=(i + 1, action["name"], action["delay"], cooldown))

    def _update_ui_state(self):
        is_running = self.macro_running
        state = tk.NORMAL if not is_running else tk.DISABLED
        
        self.add_btn.config(state=state)
        self.add_file_btn.config(state=state)
        self.edit_btn.config(state=state)
        self.del_btn.config(state=state)
        self.up_btn.config(state=state)
        self.down_btn.config(state=state)
        self.start_btn.config(state=state)
        self.stop_btn.config(state=tk.NORMAL if is_running else tk.DISABLED)
        self.profile_combo.config(state="readonly" if not is_running else tk.DISABLED)

    # --- 프로필 ---
    def _get_profile_path(self, name):
        return os.path.join(self.base_dir, "profiles", f"{name}.json")

    def _load_profile_list(self):
        profiles_dir = os.path.join(self.base_dir, "profiles")
        if not os.path.exists(profiles_dir): os.makedirs(profiles_dir)
        files = [f.replace(".json", "") for f in os.listdir(profiles_dir) if f.endswith(".json")]
        files.sort()
        self.profile_combo['values'] = files
        if files: self.profile_combo.current(0)

    def _save_current_profile(self):
        if not self.profile_combo.get():
            self._save_profile_as()
            return
        self._save_to_json(self.profile_combo.get())

    def _save_profile_as(self):
        name = simpledialog.askstring("새 프로필", "프로필 이름:")
        if name:
            self._save_to_json(name)
            self._load_profile_list()
            self.profile_combo.set(name)

    def _save_to_json(self, name):
        path = self._get_profile_path(name)
        data = {"execution_mode": self.execution_mode.get(), "actions": self.action_list}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self._log(f"프로필 저장 완료: {name}")

    def _load_selected_profile(self):
        name = self.profile_combo.get()
        if not name: return
        path = self._get_profile_path(name)
        if not os.path.exists(path): return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.action_list = data.get("actions", [])
            
            # 기존 프로필에 cooldown 필드가 없을 수 있으므로 초기화
            for action in self.action_list:
                if 'cooldown' not in action: action['cooldown'] = 0.0
                action['last_run'] = 0.0

            self.execution_mode.set(data.get("execution_mode", "sequential"))
            self._refresh_action_list()
            self._log(f"프로필 로드: {name}")
        except Exception as e:
            self._log(f"로드 실패: {e}")

    # --- 매크로 실행 ---
    def start_macro(self):
        if not self.action_list: return
        self.macro_running = True
        self._update_ui_state()
        self._log(f"매크로 시작 (모드: {self.execution_mode.get()})")
        self.macro_thread = threading.Thread(target=self._run_macro_loop)
        self.macro_thread.daemon = True
        self.macro_thread.start()

    def stop_macro(self):
        self.macro_running = False
        self._update_ui_state()
        self._log("매크로 정지 요청...")

    def _log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _run_macro_loop(self):
        mode = self.execution_mode.get()
        cycle_count = 1
        
        while self.macro_running:
            self._log(f"=== 사이클 {cycle_count} 시작 ===")
            
            if mode == "sequential":
                # [순차 실행]
                for i, action in enumerate(self.action_list):
                    if not self.macro_running: break
                    
                    name = action['name']
                    img_path = action['image_path']
                    delay = float(action['delay'])
                    cooldown = float(action.get('cooldown', 0))
                    last_run = float(action.get('last_run', 0))
                    
                    # 쿨타임 체크 (순차 모드여도 쿨타임 안 찼으면 스킵할지 대기할지? 여기선 스킵 처리)
                    # 만약 "기다려야 한다"면 로직이 복잡해짐. 보통은 스킵하거나 대기.
                    # 여기서는 쿨타임 중이면 "안 누르고 다음 순서로" 넘어가는 걸로 구현
                    if cooldown > 0 and (time.time() - last_run < cooldown):
                        self._log(f" -> [스킵] '{name}' 쿨타임 중 ({int(cooldown - (time.time() - last_run))}초 남음)")
                        continue

                    self._log(f" -> [순서 {i+1}] '{name}' 찾는 중...")
                    found = False
                    while self.macro_running and not found:
                        loc = self._find_image(img_path)
                        if loc:
                            self._click(loc)
                            action['last_run'] = time.time() # 실행 시간 갱신
                            self._log(f"   -> 클릭 완료. 대기 {delay}초")
                            time.sleep(delay)
                            found = True
                        else:
                            time.sleep(1)
                            
            else:
                # [발견 즉시 실행]
                something_clicked = False
                for action in self.action_list:
                    if not self.macro_running: break
                    
                    name = action['name']
                    img_path = action['image_path']
                    delay = float(action['delay'])
                    cooldown = float(action.get('cooldown', 0))
                    last_run = float(action.get('last_run', 0))
                    
                    # 쿨타임 체크
                    if cooldown > 0 and (time.time() - last_run < cooldown):
                        continue # 쿨타임 중이면 조용히 패스

                    loc = self._find_image(img_path)
                    if loc:
                        self._log(f" -> [발견] '{name}' 클릭!")
                        self._click(loc)
                        action['last_run'] = time.time() # 실행 시간 갱신
                        time.sleep(delay)
                        something_clicked = True
                        break # 우선순위 위해 다시 처음부터 스캔
                
                if not something_clicked:
                    time.sleep(0.5)

            if self.macro_running:
                cycle_count += 1
                time.sleep(0.5)

        self._log("매크로 종료됨.")
        self.root.after(0, self._update_ui_state)

    def _find_image(self, path):
        try:
            real_path = self._resolve_image_path(path)
            return pyautogui.locateCenterOnScreen(real_path, confidence=0.8, grayscale=True)
        except:
            return None

    def _click(self, location):
        x, y = location
        # 좌표 보정 (Retina / 2)
        calibrated_x, calibrated_y = int(x / 2), int(y / 2)
        pyautogui.click(calibrated_x, calibrated_y)

if __name__ == "__main__":
    root = tk.Tk()
    app = MacroApp(root)
    root.mainloop()
