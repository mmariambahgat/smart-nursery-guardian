import tkinter as tk

class SmartNurseryGUI:

    def __init__(self,root):
        self.root = root

        self.root.title("Smart Nursery Guardian")
        self.root.geometry("1100x800")
        self.root.minsize(900, 650)
        

        title = tk.Label(
            self.root,
            text="SMART NURSERY GUARDIAN",
            font=("Arial", 24, "bold")

        )
        title.pack(pady=15)

        status_frame =tk.LabelFrame(
            self.root,
            text="Baby and Room Status",
            font=("Arial" , 14 ,"bold")
        )

        status_frame.pack(
            fill="x",
            padx=20,
            pady=10
        )
        video_frame = tk.LabelFrame(
            self.root,
            text="  Video",
            font=("Arial",14,"bold")
            )
        video_frame.pack(
            fill="x",
            padx=20,
            pady=10
            )
        self.video_label = tk.Label(
            video_frame,
            text="No video playing",
            font=("Arial",12)
            )
        self.video_label.pack(
            padx=10,
            pady=10
            )
        

        temperature_title = tk.Label(
            status_frame,
            text="Temperature",
            font=("Arial" , 11,"bold")
        )
        temperature_title.grid(row=0 , column=0 , padx=10,pady=5)

        self.temperature_label = tk.Label(
            status_frame,
            text= "N/A",
            font=("Arial",14,"bold")
        )
        self.temperature_label.grid(row=1,column=0,padx=10,pady=5)

        baby_title = tk.Label(
            status_frame,
            text="Baby Status",
            font=("Arial" , 11,"bold")
            )
        baby_title.grid(row=0 , column=1 , padx=10,pady=5)
        
        self.baby_status_label = tk.Label(
            status_frame,
            text= "N/A",
            font=("Arial",14,"bold")
            )
        self.baby_status_label.grid(row=1,column=1,padx=10,pady=5)

        cry_title = tk.Label(
            status_frame,
            text="Cry Status",
            font=("Arial" , 11,"bold")
            )
        cry_title.grid(row=0 , column=2 , padx=10,pady=5)
        
        self.cry_status_label = tk.Label(
            status_frame,
            text= "N/A",
            font=("Arial",14,"bold")
            )
        self.cry_status_label.grid(row=1,column=2,padx=10,pady=5)

        crytype_title = tk.Label(
            status_frame,
            text="Cry Type",
            font=("Arial" , 11,"bold")
            )
        crytype_title.grid(row=0 , column=3 , padx=10,pady=5)
        
        self.cry_type_label = tk.Label(
            status_frame,
            text= "N/A",
            font=("Arial",14,"bold")
            )
        self.cry_type_label.grid(row=1,column=3,padx=10,pady=5)

        gas_title = tk.Label(
            status_frame,
            text="Gas Status",
            font=("Arial" , 11,"bold")
            )
        gas_title.grid(row=2 , column=0 , padx=10,pady=5)
        
        self.gas_status_label = tk.Label(
            status_frame,
            text= "N/A",
            font=("Arial",14,"bold")
            )
        self.gas_status_label.grid(row=3,column=0,padx=10,pady=5)

        light_title = tk.Label(
            status_frame,
            text="Light Status",
            font=("Arial" , 11,"bold")
            )
        light_title.grid(row=2 , column=1 , padx=10,pady=5)
        
        self.light_status_label = tk.Label(
            status_frame,
            text= "N/A",
            font=("Arial",14,"bold")
            )
        self.light_status_label.grid(row=3,column=1,padx=10,pady=5)

        esp_title = tk.Label(
            status_frame,
            text="ESP32 connection",
            font=("Arial" , 11,"bold")
            )
        esp_title.grid(row=2 , column=2 , padx=10,pady=5)
        
        self.esp_status_label = tk.Label(
            status_frame,
            text= "N/A",
            font=("Arial",14,"bold")
            )
        self.esp_status_label.grid(row=3,column=2,padx=10,pady=5)

        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=10
        )

        alert_frame = tk.LabelFrame(
            self.root,
            text="Alerts",
            font=("Arial",14,"bold")
        )

        alert_frame.pack(
            in_=bottom_frame,
            side="left",
            fill="both",
            expand=True,
            padx=(0,5),
            pady=0
        )
        self.alert_text= tk.Text(
            alert_frame,
            height=10,
            state="disabled",
            wrap="word",
            font=("Arial",11)
        )
        self.alert_text.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        message_frame = tk.LabelFrame(
            self.root,
            text="Messages",
            font=("Arial",14,"bold")
        )
        
        message_frame.pack(
            in_=bottom_frame,
            side="right",
            fill="both",
            expand=True,
            padx=(5,0),
            pady=0
        )
        self.message_text= tk.Text(
            message_frame,
            height=10,
            state="disabled",
            wrap="word",
            font=("Arial",11)
        )
        self.message_text.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        clear_alerts_button = tk.Button(
            button_frame,
            text="Clear Alerts",
            command=self.clear_alerts,
            font=("Arial",11),
            width=15
        )
        clear_alerts_button.pack(
            side="left",
            padx=10
        )
        clear_message_button = tk.Button(
            button_frame,
            text="Clear Messages",
            command=self.clear_messages,
            font=("Arial",11),
            width=15
            )
        clear_message_button.pack(
            side="left",
            padx=10
            )
        exit_button = tk.Button(
            button_frame,
            text="Exit",
            command=self.root.destroy,
            font=("Arial",11),
            width=15
            )
        exit_button.pack(
            side="left",
            padx=10
            )




    def update_temperature(self , temp):
        self.temperature_label.config(text=f"{temp} °C")
        
    def update_baby_status(self , status):
        self.baby_status_label.config(text=status)
        
    def update_cry_status(self , status):
        self.cry_status_label.config(text=status)

    def update_cry_type(self , cry_type):
        self.cry_type_label.config(text=cry_type)

    def update_gas_status(self , status):
        self.gas_status_label.config(text=status)

    def update_light_status(self , status):
        self.light_status_label.config(text=status)

    def update_esp_status(self , status):
        self.esp_status_label.config(text=status)
    
    def update_video_status(self,status):
        self.video_label.config(text=status)

    def show_alert(self,message):
        self.alert_text.config(state="normal")

        self.alert_text.insert("end", f"ALERT:{message}\n")
        self.alert_text.see("end")
        self.alert_text.config(state="disabled")

    def clear_alerts(self):
        self.alert_text.config(state="normal")

        self.alert_text.delete("1.0", "end")
        self.alert_text.config(state="disabled")

    def update_message(self,message):
        self.message_text.config(state="normal")
        self.message_text.insert("end",f"{message}\n")
        self.message_text.see("end")
        self.message_text.config(state="disabled")

    def clear_messages(self):
            self.message_text.config(state="normal")
            self.message_text.delete("1.0","end")
            self.message_text.config(state="disabled")
            
    def run_gui(self):
        self.root.mainloop()


    
    
        

if __name__ =="__main__":
    root =tk.Tk()
    app = SmartNurseryGUI(root)
    # # #test data
    # app.show_alert("Gas detected")
    # app.update_message("Baby is hungry")
    # app.update_message("Calming video play")
    # app.update_temperature(28.5)
    # app.update_baby_status("Awake")
    # app.update_cry_status("Crying")
    # app.update_cry_type("Hungry")
    # app.update_gas_status("Normal")
    # app.update_light_status("Lights on")
    # app.update_esp_status("Connected")

    app.run_gui()
