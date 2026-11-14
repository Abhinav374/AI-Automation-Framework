class Dog:
     # Attributes - Instance variables | Data variables
    name = None
    breed = None
    height = None
    weight = None
    race = None

    def __init__(self,nameGiven,breedGiven):  # Default C - No Parameter
        print("Hi")
        self.name=nameGiven
        self.breed=breedGiven

    def bark(self):
        print("Barking!->",self.name)
    def talk(self):
        print("talking")


chow=Dog("chow","mastif")
chow.bark()

desi=Dog("rancho","desi")
desi.bark()

#strydog=Dog()