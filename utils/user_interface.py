# works for dictionaries
# lists of dictionaries
# dictionaries with values being handled types
import tkinter as tk


class DictChecker(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.minsize(width=300, height=50)
        self.pack()
        self.table = None

    def check_dict(self, d, modify):
        table = tk.Frame(self.master)
        entries = dict()
        for (n, (k, v)) in enumerate(d.items()):
            label = tk.Label(table, text=str(k))
            label.grid(row=n, column=1, sticky="nsew")
            ent = tk.Entry(table, textvariable=tk.StringVar(value=str(v)))
            ent.grid(row=n, column=2, sticky="nsew")
            if isinstance(v, dict):
                self.check_dict(v, modify)
            elif isinstance(v, list):
                if len(v) > 0 and isinstance(v[0], dict):
                    for q in v:
                        self.check_dict(q, modify)
            else:
                entries[k] = ent
        table.pack()

        var = tk.IntVar()
        button = tk.Button(self.master, text="I'm done", command=lambda: var.set(1))
        button.bind_all("<Return>", lambda _: var.set(2))
        button.pack(side='bottom')
        button.wait_variable(var)

        if modify:
            modified_entries = {}
            for k in entries:
                u = entries[k].get()
                if u.lower() == "true":
                    modified_entries[k] = True
                elif u.lower() == "false":
                    modified_entries[k] = False
                elif any(kkk in k.lower()
                         for kkk in ['tax', 'wage', 'dividend', 'interest', 'proceeds', 'cost', 'value']):
                    modified_entries[k] = float(u)
                else:
                    modified_entries[k] = u
            d.update(modified_entries)

        button.destroy()
        table.destroy()

    def close(self):
        self.master.destroy()


# this si the exported function
def update_dict(d, modify=True):
    root = tk.Tk()
    root.title("Input Parser")
    root.attributes('-topmost', True)
    app = DictChecker(master=root)
    app.check_dict(d, modify)
    app.close()
    app.mainloop()


# this is just for testing
def main():
    root = tk.Tk()
    root.title("Input Parser")
    root.attributes('-topmost', True)
    app = DictChecker(master=root)
    d = {'oui': 'ouioui', 'no': 'nono'}
    app.check_dict(d)
    app.close()
    app.mainloop()
    print(d)


if __name__ == '__main__':
    main()
