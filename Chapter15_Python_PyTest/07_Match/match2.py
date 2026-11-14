status =400

match status: 
    case 200 | 201:print("request successful")
    case 400:print("Bad request")
    case 401:print("Unathourized")
    case 500:print("server error")
    case _: print("unknown status")
    
    
