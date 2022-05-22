# Copyright (c) 2022, Pivottech and contributors
# For license information, please see license.txt

from itertools import count
import frappe
from frappe.model.document import Document
from frappe.utils.xlsxutils import (
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)
from frappe.utils import flt, add_days, formatdate
from frappe import _

class ticketEntry(Document):
	def has_back(self):
		#check if this ticket has back(return) journey or not 
		return self.back_date and self.back_routing and self.back_flight_no
	
	def insert_route(self, route, last_routing):
		date_arr = route[3:]
		date_arr.reverse()
		date_str = " ".join(date_arr)
		if self.has_back() or last_routing == route[2]:
			self.back_flight_no = self.back_flight_no + "-" + route[1] if self.back_flight_no else route[1]
			self.update_routing(route[2], True)
			self.back_date = self.back_date + " " + date_str if (self.back_date and self.back_date != date_str) else date_str
		else:
			self.departure_flight_no = self.departure_flight_no + "-" + route[1] if self.departure_flight_no else route[1]
			self.update_routing(route[2])
			self.departure_date = self.departure_date + " " + date_str if (self.departure_date and self.departure_date != date_str) else date_str

	def update_routing (self, routing, is_back=False):
		if is_back:
			self.back_routing = self.back_routing.strip()[:-3] + routing if self.back_routing else routing
		else:
			self.departure_routing = self.departure_routing.strip()[:-3] + routing if self.departure_routing else routing
	
	def handle_routing(self, last_routing, routing):
		route = routing.split(" ")
		route.reverse()
		if route[0] == "CNX":
			return last_routing

		self.insert_route(route, reverse_routing(last_routing))
		return route[2]
			
@frappe.whitelist()
def insert_tickets(filepath):
	data = read_excel(filepath)
	count = 0
	for row in data:
		count += 1
		frappe.publish_progress(count*100/len(data), title=_("Importing Ticket Entries"), description = row["pnr"])
		d = frappe._dict(row)
		ticket_entry = frappe.new_doc("ticket Entry")
		if d.pnr:
			d.e_ticket = str(d.e_ticket)
			e_tickets = d.e_ticket.split("-")
			etickets_float = [flt(et[3:],0) for et in e_tickets]
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
					"passenger": d.passenger_name,
					"nationality": d.natationality
				}).insert()
			ticket_entry.passenger = d.passenger_name
			#routing
			routings = d.routing.split(";")
			last_routing = None
			for r in routings:
				last_routing = ticket_entry.handle_routing(last_routing, r.strip())
			#standard fields
			standard_fields = ["fare_amount", "payment_mode", "tax_amount", "charge_amount", "modify_amount", "total_amount", "sales", "pax_name", "natationality"]
			for sf in standard_fields:
				setattr(ticket_entry, sf, d[sf])
			#non standard fields
			if type(d.payment_date) is not str:
				ticket_entry.payment_date = add_days("1/1/1900", d.payment_date-2)
			else:
				formatdate(d.payment_date, "dd-MMM-yy")
			ticket_entry.user = d.user_name
			ticket_entry.refund_amount = d.re_found_amount
			ticket_entry.supp_com = d["supp_com%"]
			ticket_entry.sales_com = d["sales_com%"]
			ticket_entry.currency = d["curr."]
			ticket_entry.conversion_rate = d.rate

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
	


	
#08-APR-22 DAM/NJF 6Q511 CNX ; OPEN RETURN  NJF/DAM 6Q512 CNX
def reverse_routing(r):
#revers routing to check back route 
#ex: DAM/SHJ => SHL/Dam
	if not r:
		return ""
	rs = r.split("/")
	rs.reverse()
	return "/".join(rs)
	