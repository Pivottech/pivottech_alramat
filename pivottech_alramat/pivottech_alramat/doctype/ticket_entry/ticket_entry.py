# Copyright (c) 2022, Pivottech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.xlsxutils import (
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)
from frappe.utils import flt

class ticketEntry(Document):
	pass


@frappe.whitelist()
def insert_tickets(filepath):
	data = read_excel(filepath)
	for row in data:
		d = frappe._dict(row)
		ticket_entry = frappe.new_doc("ticket Entry")
		if d.pnr:
			d.e_ticket = str(d.e_ticket)
			e_tickets = d.e_ticket.split("-")
			etickets_float = [flt(et[3:]) for et in e_tickets]
			#pnr
			ticket_entry.pnr = d.pnr
			#E-Ticket
			ticket_entry.airline_company_code = d.e_ticket[0:3]
			ticket_entry.airline_company = frappe.db.get_value("Airline Code", d.e_ticket[0:3], "airline_company")
			ticket_entry.eticket = str(max(etickets_float))
			#Passenger
			if not frappe.get_list("passenger name", filters={"name": d.passenger_name}):
				frappe.get_doc({
					"doctype": "passenger name",
					"passenger": d.passenger_name
				}).insert()
			ticket_entry.passenger = d.passenger_name
			#Payment Mode
			ticket_entry.payment_mode = d.payment_mode
			ticket_entry.insert()
			





def read_excel(filepath):
	file_doc, extension = get_file(filepath)
	data = generate_data_from_excel(file_doc, extension, as_dict=True)
	return data


def get_file(file_name):
	file_doc = frappe.get_doc("File", {"file_url": file_name})
	parts = file_doc.get_extension()
	extension = parts[1]
	extension = extension.lstrip(".")

	if extension not in (  'xlsx', 'xls'):
		frappe.throw(_("Only Excel files can be used to for importing data. Please check the file format you are trying to upload"))

	return  file_doc, extension

def generate_data_from_excel(file_doc, extension, as_dict=False):
	content = file_doc.get_content()

	if extension == "xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content)
	elif extension == "xls":
		rows = read_xls_file_from_attached_file(content)

	data = []
	headers = rows[0]
	del rows[0]

	for row in rows:
		if as_dict:
			data.append({frappe.scrub(header): row[index] for index, header in enumerate(headers)})
		else:
			if not row[1]:
					row[1] = row[0]
					row[3] = row[2]
			data.append(row)

	return data