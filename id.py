import string
import secrets

def gen_objective_id():
  return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))

def gen_scoreholder_id():
  return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))

def gen_function_id():
  return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))