# Declare a variable named `name` and assign it the value "Hello World"
print("Hello World")
#write a comment that describes "This is a comment"
# This is a comment
#log a message to the console that says "I AM A COMPUTER"
print("I AM A COMPUTER")
#write a statement that 4 is greater than 2 and 1 is less than 2.
print(4 > 2 and 1 < 2)
#assign the value None to an absent variable named `A`
nope=None
#use the language "and" boolean operator to check if 5 is greater than 3 and 5 is less than 4.
print(5 > 3 and 5 < 4)
#calculate the length of a string "What is my length?" and assign it to a variable named `length`
length = len("What is my length?")
print(length)
#convert the string "i am shouting" to all uppercase letters and assign it to a variable named `lowercase`
lowercase = "i am shouting".upper()
print(lowercase)
#convert the string"1000" to an integer and assign it to a variable named `1000`
score= int("1000")
print(score)
#combine the numbers 4  with a string "real"
print(str(4) + "real")
#record the output of the expression3*"cool"
print(3 * "cool")
#record the output of the expression 1/0
try:
    (1/0)
except ZeroDivisionError:
    print(" ZeroDivisionError ")
#determine the type of []
print(type([]))
#ask the user for their name and store it in a variable named `name`
name = input("What is your name? ")
print(name)
#ask the user for a number .if the number is negative, print "negative number". "That number is less than 0".  
number = float(input("Please enter a number: "))
if number < 0:
    print("negative number. That number is less than 0.")
elif number > 0:
    print("positive number. That number is greater than 0.")
else:
    print("zero. That number is equal to 0.")
    #find the index "1" in"apple"
    print("apple".index("1"))
    #check whether "y"is in "xylophone"
    print("y" in "xylophone")
    #check whether a string called my_string is all lowercase.
    my_string = "Hello, World!"
    print(my_string.islower())
