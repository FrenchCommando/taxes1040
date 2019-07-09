myTaxes

Fills federal taxes for 2018

Forms are put in the 'forms' folder

To automatically fill taxes
- put personal files (W2.pdf, 1099.xml) in 'input_data' folder
- run 'main.py'
- it opens a windows in which you can override some information
- output is in 'forms.pdf'

Currently most of the configs are set for single resident with no dependent.
The code is modular enough such that changes can be implemented easily.

Can't fill NY forms because they are 'enhanced' 
-> don't know how to manipulate them in python
