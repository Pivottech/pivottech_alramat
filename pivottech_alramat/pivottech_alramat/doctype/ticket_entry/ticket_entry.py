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
	def validate(self):
		self.total_amount = flt(self.tax_amount) + flt(self.charge_amount) + flt(self.fare_amount) + flt(self.modify_amount)
		if not self.edit_commissions: 
			self.calculate_discount()
			self.calculate_commission()
			self.calculate_totals()
			self.calculate_user_commission()
		else:
			self.validate_discount()
			self.validate_commission()
			self.calculate_totals()
	
	def before_insert(self):
		self.validate_duplicate_e_ticket()

	def validate_discount(self):
		amount = self.total_amount if self.from_total else self.fare_amount
		if self.sales_com:
			self.discount = flt(amount) * flt(self.sales_com) /100
		if self.discount:
			self.sales_com = flt(self.discount) * 100 / flt(amount)
	
	def validate_commission(self):
		amount = self.total_amount if self.from_total else self.fare_amount
		if self.supp_com:
			self.commission_ = flt(amount) * flt(self.supp_com) /100
		elif self.commission_:
			self.supp_com = flt(self.commission_) * 100 / flt(amount) 

	def calculate_discount(self):
		if self.customer and self.vendor:
			customer_level = frappe.db.get_value("Customer", self.customer, "commission_level")
			customer_comms = frappe.get_list("air line company commission", filters={
				"parenttype": "Customer level",
				"parent": customer_level,
				"supplier": self.vendor,
				"airline_company": self.airline_company_code
			}, pluck="name")
			commission = get_discount_or_commission(customer_comms, self.departure_routing)
			total = self.fare_amount if commission.sourcerouting == "Fare" else self.total_amount
			self.discount = flt(total) * flt(commission.com)/100 + flt(commission.discount)
			self.sales_com = self.discount * 100 / total
				
	def calculate_commission(self):
		if self.vendor:
			supplier_comms = frappe.get_list("air line company commission", filters={
				"parenttype": "Supplier",
				"airline_company": self.airline_company_code,
				"parent": self.vendor
			}, pluck="name")
			commission = get_discount_or_commission(supplier_comms, self.departure_routing)
			total = self.fare_amount if commission.sourcerouting == "Fare" else self.total_amount
			self.commission_ = flt(total) * flt(commission.com)/100 + flt(commission.discount)
			self.supp_com = self.commission_ * 100 / total
	
	def calculate_user_commission(self):
		if self.user and self.vendor:
			employee_comms = frappe.get_list("user commission", filters={
				"parenttype": "Employee",
				"airline_company": self.airline_company_code,
				"supplier": self.vendor,
				"parent": self.user
			}, pluck="name")
			commission = get_user_commission(employee_comms, self.departure_routing)
			self.user_commission = flt(self.profit) * flt(commission.com)/100  if flt(commission.com) else flt(commission.discount)	
				
	def calculate_totals(self):
		self.net_price = flt(self.total_amount) - flt(self.commission_)
		if self.total_amount and self.discount:
			self.sales = flt(flt(self.total_amount) - flt(self.discount), -2)
		if self.sales and self.net_price:
			self.profit = flt(flt(self.sales) - flt(self.net_price))

	def validate_duplicate_e_ticket(self):
		if(frappe.db.exists("ticket Entry", {"eticket": self.eticket, "total_amount":[">", 0]})):
			if flt(self.total_amount) > 0:
				frappe.throw("Cannot add Dublicate E Ticket with Possitive Total Amount for e-ticket: %s"%self.eticket)
			else:
				frappe.msgprint("Dublicate E Ticket for e-ticket: %s"%self.eticket)
		
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
		if route[0] == "CNX" and not self.cancelled:
			return last_routing

		self.insert_route(route, reverse_routing(last_routing))
		return route[2]

	def check_void_or_refund(self, routing):
		routings = routing.split(";")
		has_cnx = has_cnf = False
		for r in routings:
			sub_route_arr = r.strip().split(" ")
			sub_route_arr.reverse()
			if sub_route_arr[0] == "CNX":
				has_cnx = True
			if sub_route_arr[0] == "CNF":
				has_cnf = True
		if has_cnf and flt(self.total_amount) < 0:
			self.refund = True
		if not has_cnf and has_cnx:
			self.cancelled = True


def get_discount_or_commission(commissions, routing):
	if not commissions:
		return frappe._dict({
			"com": 0,
			"discount": 0,
			"sourcerouting": "Fare"
		})
	departure_arrival_comms = frappe.get_list("air line company commission", filters={
					"name":["in", commissions],
					"departure": ["like", routing.split("/")[0]],
					"arrival": ["like", routing.split("/")[-1]]
				}, fields=["name", "com", "discount", "sourcerouting"])
	if departure_arrival_comms:
		return departure_arrival_comms[0]
	
	departure_comms = frappe.get_list("air line company commission", filters={
					"name":["in", commissions],
					"departure": ["like", routing.split("/")[0]],
					"arrival": ""
				}, fields=["name", "com", "discount", "sourcerouting"])
	if departure_comms:
		return departure_comms[0]
	
	return frappe.db.get_value("air line company commission", commissions[0], ["com_company as com", "dis_com as discount", "source as sourcerouting"], as_dict=1)

def get_user_commission(commissions, routing):
	if not commissions:
		return frappe._dict({
			"com": 0,
			"discount": 0,
		})
	departure_arrival_comms = frappe.get_list("user commission", filters={
					"name":["in", commissions],
					"departure": ["like", routing.split("/")[0]],
					"arrival": ["like", routing.split("/")[-1]]
				}, fields=["name", "com", "discount"])
	if departure_arrival_comms:
		return departure_arrival_comms[0]
	
	departure_comms = frappe.get_list("user commission", filters={
					"name":["in", commissions],
					"departure": ["like", routing.split("/")[0]],
					"arrival": ""
				}, fields=["name", "com", "discount"])
	if departure_comms:
		return departure_comms[0]

	return frappe.db.get_value("user commission", commissions[0], ["com_company as com", "dis_com as discount"], as_dict=1)

		

@frappe.whitelist()
def insert_tickets(filepath):
	data = read_excel(filepath)
	count = 0
	for row in data:
		d = frappe._dict(row)
		unfilled_fields = validate_excel_row(d)
		if unfilled_fields:
			frappe.throw("Some Fields are Required in Excel File: "+unfilled_fields)
		count += 1
		ticket_entry = frappe.get_doc({"doctype": "ticket Entry"})
		if d.pnr:
			frappe.publish_progress(count*100/len(data), title=_("Importing Ticket Entries"), description = d.pnr)
			d.e_ticket = str(d.e_ticket)
			e_tickets = d.e_ticket.split("-")
			e_tickets = handle_e_tickets(e_tickets)
			etickets_float = [flt(et[3:],0) for et in e_tickets]
			#E-Ticket
			from_sales_order_et = frappe.get_list("ticket Entry", filters={
				"eticket": str(max(etickets_float)),
				"status": "Hold"
			}, pluck="name")
			if from_sales_order_et:
				ticket_entry = frappe.get_doc("ticket Entry", from_sales_order_et[0])

			ticket_entry.eticket = str(max(etickets_float))
			ticket_entry.airline_company_code = e_tickets[0][0:3]
			ticket_entry.airline_company = frappe.db.get_value("Airline Code", d.e_ticket[0:3], "airline_company")
			
			#pnr
			ticket_entry.pnr = d.pnr
			#Passenger
			if not frappe.get_list("passenger name", filters={"name": d.passenger_name}):
				frappe.get_doc({
					"doctype": "passenger name",
					"passenger": d.passenger_name,
					"nationality": d.natationality if d.natationality else ""
				}).insert()
			ticket_entry.passenger = d.passenger_name

			#pax name
			pn = frappe.db.get_list("Customer", filters={"name": d["pax_name"]}, pluck="name")
			ticket_entry.pax_name = pn[0] if pn else ""
			
			#Customer
			customer = frappe.get_list("Customer", filters={"email_id": d["account_code"], "default_currency": d["curr."]}, fields=["name"])
			if customer: 
				ticket_entry.customer = customer[0].name

			#Supplier
			ticket_entry.vendor = frappe.db.get_value("Supplier", {"code": d["vendor"]}, "name")

			#standard fields
			standard_fields = ["fare_amount", "payment_mode", "tax_amount", "charge_amount", "modify_amount", "sales", "natationality"]
			for sf in standard_fields:
				if sf in d:
					setattr(ticket_entry, sf, d[sf])

			#refund void
			ticket_entry.check_void_or_refund(d.routing.strip())
			#routing
			routings = d.routing.split(";")
			last_routing = None
			for r in routings:
				last_routing = ticket_entry.handle_routing(last_routing, r.strip())
			#non standard fields
			if type(d.payment_date) is not str:
				ticket_entry.payment_date = add_days("1/1/1900", d.payment_date-2)
			else:
				formatdate(d.payment_date, "dd-MMM-yy")
			
			#user
			user = frappe.get_list("Employee", filters=
				{"employee_name": d.user},
				fields=["name", "employee_name"])
			if user:
				ticket_entry.user = user[0].name
				ticket_entry.user_name = user[0].employee_name
			ticket_entry.refund_amount = d.re_found_amount
			#ticket_entry.sales_com = d["com%"]
			#ticket_entry.supp_com = d["sales_com"]
			ticket_entry.currency = d["curr."]
			ticket_entry.conversion_rate = d["rate"]
			ticket_entry.status = "Saved"
			if from_sales_order_et:
				ticket_entry.save()
			else:
				ticket_entry.insert()
	frappe.publish_progress(100, title=_("Importing Ticket Entries"))
			
			

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
	remove_extra_rows(rows)
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

def remove_extra_rows(rows):
	index = -1
	for i in range(len(rows)):
		if check_if_header(rows[i]):
			index = i
			break
	del rows[:index]		

def check_if_header(row):
	return "PNR" in row and "E-Ticket" in row and "Passenger Name" in row

def handle_e_tickets(e_tickets):
	#if e ticket has less than 13 charachters it will add zeros at the first
	new_list = []
	for et in e_tickets:
		et = str(flt(et, 0))
		char_diff = 13 - len(et)
		if char_diff:
			et = str(char_diff*"0" + str(et))
			
		new_list.append(et)
	return new_list
	
#08-APR-22 DAM/NJF 6Q511 CNX ; OPEN RETURN  NJF/DAM 6Q512 CNX
def reverse_routing(r):
#revers routing to check back route 
#ex: DAM/SHJ => SHL/Dam
	if not r:
		return ""
	rs = r.split("/")
	rs.reverse()
	return "/".join(rs)
	
def validate_excel_row(d):
	res = []
	for i in ["pnr", "e_ticket", "passenger_name", "routing", "pax_name", "total_amount"]:
		if i not in d:
			res.append(i)
	return ",".join(res)
