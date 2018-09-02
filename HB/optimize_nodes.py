from __future__ import print_function
from values import MyGlobals, initialize_params
import misc
from os import path 
from itertools import product
import sys
sys.path.insert(0, '../fuzzer')

from check import *
import op_parse
import op_exec
from op_exec import print_balance_difference, pad_address
import codecs

def preprocess(contract_address, trace_new, nodes):
# Clear all parameters
	op_exec.clear_params()
	op_exec.set_params('contract_address','',contract_address )

	# Set balances
	set_balances(trace_new, contract_address.lstrip('0x'), nodes)

def cart_input(inputstr):
	input_dict = {}
	length = len(inputstr)
	no_inputs = (len(inputstr)-8)//64
	mutable = [0 for i in range(0, no_inputs)]
	mutable_positions = []
	final_input_strings = []

	# Find the mutable inputs
	for i in range(no_inputs):
		temp_str = inputstr[8+i*64:8+i*64+64]

		if int(temp_str, 16) < 2**30 or int(temp_str, 16) > int('f'*40, 16):
			mutable[i] = 1
			mutable_positions.append(i)
	immutable_positions = list(set(i for i in range(0, no_inputs))-set(mutable_positions))		

	all_poss = list(product(range(2), repeat = no_inputs))
	all_poss.sort(key=sum, reverse=True)

	for each_tuple in all_poss:
		found = True
		for pos in immutable_positions:
			if not mutable[pos] == each_tuple[pos]:
				found = False
				break

		if found:
			string1 = inputstr[0:8]
			string2 = inputstr[0:8]
			count = 0
			for eachpos in each_tuple:
				if 0 == eachpos:
					string1 += inputstr[8+count*64:8+count*64+64]
					string2 += inputstr[8+count*64:8+count*64+64]

				if 1 == eachpos:
					string1 += '1'.rjust(64,'0')
					string2 += '3'.rjust(64,'0')	

				count+=1	
			final_input_strings.append(string1)
			input_dict[string1] = string2

				

	return final_input_strings, input_dict	

def add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2):
	if add1 and add2 : new_hb.append((len(new_nodes)-2, len(new_nodes)-1))
	if (not add1) and add2: new_hb.append((new_nodes.index(candidate1), len(new_nodes)-1))
	if (not add2) and add1: new_hb.append((len(new_nodes)-1, new_nodes.index(candidate2)))
	if (not add1) and (not add2):
		if not (new_nodes.index(candidate1), new_nodes.index(candidate2)) in new_hb: 
			new_hb.append((new_nodes.index(candidate1), new_nodes.index(candidate2)))


def optimize_nodes(nodes, hb, contract_address, code, debug, read_from_blockchain, st_blocknumber):
	print('\n......Optimizing the inputs......\n')
	node_count = {}
	for node in nodes:
		if node['name'] in node_count:
			node_count[node['name']]+=1
		else:
			node_count[node['name']] = 1

	new_nodes = []		
	new_hb = []
	hb_list = []
	changed_dict = {}

	for each in hb:
		if not each[0] in hb_list:
			hb_list.append(each[0])
		if not each[1] in hb_list:
			hb_list.append(each[1])		

	no_hb_list = list(set( i for i in range(0, len(nodes))) - set(hb_list))


	for i in range(0, len(no_hb_list)):
		candidate = nodes[no_hb_list[i]]

		if not 'tx_input' in candidate:
			new_nodes.append(copy.deepcopy(candidate))
			continue

		function_input = candidate['tx_input']
		list_inputs, input_dict = cart_input(candidate['tx_input'])
		for each_input in list_inputs:
			candidate['tx_input'] = each_input
			storage = {}
			preprocess(contract_address, [no_hb_list[i]], nodes)
			ct = check_one_trace(contract_address, [candidate], storage, code, debug, read_from_blockchain, st_blocknumber)
			
			if ct: break

		if not ct:	candidate['tx_input'] = function_input	
		new_nodes.append(copy.deepcopy(candidate))
	
	# For the nodes in HB
	for i in range(0, len(hb)):
		candidate1 = nodes[hb[i][0]]
		candidate2 = nodes[hb[i][1]]
		# if not (hb[i][0], hb[i][1])	in new_hb:
		# 	new_hb.append((hb[i][0], hb[i][1]))

		if 'tx_input' in candidate1:
			list_inputs1, input_dict1= cart_input(candidate1['tx_input'])
		if 'tx_input' in candidate2:
			list_inputs2, input_dict2= cart_input(candidate2['tx_input'])

		ct1 = False
		ct2 = False
		found = False
		function_input1 = candidate1['tx_input']
		function_input2 = candidate2['tx_input']


		if 'tx_input' in candidate1:

			for each_input1 in list_inputs1:
				candidate1['tx_input'] = each_input1
				storage = {}
				preprocess(contract_address, [hb[i][0]], nodes)
				ct1 = check_one_trace(contract_address, [candidate1], storage, code, debug, read_from_blockchain, st_blocknumber)
				# if ct1:
				# 	storage = {}
				# 	preprocess(contract_address, [hb[i][0], hb[i][1]], nodes)
				# 	ct2 = check_one_trace(contract_address, [candidate1, candidate2], storage, code, debug, read_from_blockchain, st_blocknumber)

				if 'tx_input' in candidate2 and ct1: #and ct2:
					for each_input2 in list_inputs2:
						candidate2['tx_input'] = each_input2
						storage = {}
						preprocess(contract_address, [hb[i][0], hb[i][1]], nodes)
						ct2 = check_one_trace(contract_address, [candidate1, candidate2], storage, code, debug, read_from_blockchain, st_blocknumber)
						
						if ct2:
							add1 = False
							add2 = False

							if not candidate1 in new_nodes:
								add1 = True
								new_nodes.append(copy.deepcopy(candidate1))
							if not candidate2 in new_nodes:	
								add2 = True
								new_nodes.append(copy.deepcopy(candidate2))
							# Adding the nodes to HB
							add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)
							
							add1 = False
							add2 = False	
							# if node_count[candidate1['name']] < MyGlobals.max_solutions:
							candidate1['tx_input'] = input_dict1[each_input1]
							if not candidate1 in new_nodes:
								add1 = True
								new_nodes.append(copy.deepcopy(candidate1))
								node_count[candidate1['name']]+=1
							# if node_count[candidate2['name']] < MyGlobals.max_solutions:
							candidate2['tx_input'] = input_dict2[each_input2]
							if not candidate2 in new_nodes:
								add2 = True
								new_nodes.append(copy.deepcopy(candidate2))
								node_count[candidate2['name']]+=1

							# Adding the nodes to HB
							add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)
							found = True
							break

					if found: break
				
				elif not 'tx_input' in candidate2 and ct1:
					storage = {}
					preprocess(contract_address, [hb[i][0], hb[i][1]], nodes)
					ct2 = check_one_trace(contract_address, [candidate1, candidate2], storage, code, debug, read_from_blockchain, st_blocknumber)	
					if ct2:
						add1 = False
						add2 = False
						if not candidate1 in new_nodes:
							add1 = True
							new_nodes.append(copy.deepcopy(candidate1))
						if not candidate2 in new_nodes:
							add2 = True
							new_nodes.append(copy.deepcopy(candidate2))

						# Adding the nodes to HB
							add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)
								
						# if node_count[candidate1['name']] < MyGlobals.max_solutions:
						add1 = False
						candidate1['tx_input'] = input_dict1[each_input1]
						if not candidate1 in new_nodes:
							add1 = True
							new_nodes.append(copy.deepcopy(candidate1))
							node_count[candidate1['name']]+=1

						# Adding the nodes to HB
						add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)	
						
						found = True
						break

			if not found:
				candidate1['tx_input'] = function_input1
				candidate2['tx_input'] = function_input2
				add1 = False
				add2 = False

				if not candidate1 in new_nodes:
					add1 = True
					new_nodes.append(copy.deepcopy(candidate1))
				if not candidate2 in new_nodes:
					add2 = True
					new_nodes.append(copy.deepcopy(candidate2))

				# Adding the nodes to HB
				add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)
					

		else:

			for each_input2 in list_inputs2:
				candidate2['tx_input'] = each_input2
				storage = {}
				preprocess(contract_address, [hb[i][0], hb[i][1]], nodes)
				ct2 = check_one_trace(contract_address, [candidate1, candidate2], storage, code, debug, read_from_blockchain, st_blocknumber)			

				if ct2: 
					add1 = False
					add2 = False
					if not candidate1 in new_nodes:
						add1= True
						new_nodes.append(copy.deepcopy(candidate1))
					if not candidate2 in new_nodes:
						add2 = True
						new_nodes.append(copy.deepcopy(candidate2))

					# Adding the nodes to HB
					add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)	
					
					add2 = False
					# if node_count[candidate2['name']] < MyGlobals.max_solutions:
					candidate2['tx_input'] = input_dict2[each_input2]
					if not candidate2 in new_nodes:
						add2 = True
						new_nodes.append(copy.deepcopy(candidate2))
						node_count[candidate2['name']]+=1

					# Adding the nodes to HB
					add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)	
					found = True
					break

			
			if not found: 

				candidate2['tx_input'] = function_input2
				add1 = False
				add2 = False
				if not candidate1 in new_nodes:
					add1 = True
					new_nodes.append(copy.deepcopy(candidate1))
				if not candidate2 in new_nodes:
					add2 = True
					new_nodes.append(copy.deepcopy(candidate2))

				# Adding the nodes to HB
				add_hb(add1, add2, new_nodes, new_hb, candidate1, candidate2)


	return new_nodes, new_hb