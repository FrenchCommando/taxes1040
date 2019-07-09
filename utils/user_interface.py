import tkinter as tk


class DictChecker(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.minsize(width=300, height=50)
        self.pack()
        self.table = None

    def check_dict(self, d):
        self.table = tk.Frame(self.master)
        entries = dict()
        for (n, (k, v)) in enumerate(d.items()):
            label = tk.Label(self.table, text=str(k))
            label.grid(row=n, column=1, sticky="nsew")
            ent = tk.Entry(self.table, textvariable=tk.StringVar(value=str(v)))  # ,width=30)
            ent.grid(row=n, column=2, sticky="nsew")
            entries[k] = ent
        self.table.pack()

        var = tk.IntVar()
        button = tk.Button(self.master, text="I'm done", command=lambda: var.set(1))
        button.pack(side='bottom')

        button.wait_variable(var)
        saisies = dict()
        for k, v in d.items():
            u = entries[k].get()
            if u.lower() == "true":
                saisies[k] = True
            elif u.lower() == "false":
                saisies[k] = False
            else:
                saisies[k] = u
        return saisies

    def close(self):
        self.master.destroy()


def update_dict(d):
    root = tk.Tk()
    root.title("Input Parser")
    root.attributes('-topmost', True)
    app = DictChecker(master=root)
    d.update(app.check_dict(d))
    app.close()
    app.mainloop()


def main():
    root = tk.Tk()
    root.title("Input Parser")
    root.attributes('-topmost', True)
    app = DictChecker(master=root)
    d = {'oui': 'ouioui', 'no': 'nono'}
    d.update(app.check_dict(d))
    app.close()
    app.mainloop()
    print(d)


if __name__ == '__main__':
    main()
