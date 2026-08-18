person_list = [("name", "Elie"), ("job", "Instructor")]
print(person_list)

# Using dict() constructor directly:
person_dict = dict(person_list)
print(person_dict)

# Or using dictionary comprehension:
# person_dict = {key: value for key, value in person_list}
print(person_dict)

print(person_dict)
print(person_dict)
# Output: {'name': 'Elie', 'job': 'Instructor'}
print(person_dict["name"])  # Output: Elie