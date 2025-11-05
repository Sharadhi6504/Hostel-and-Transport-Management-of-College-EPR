from typing import Optional

class Student:
    def __init__(self, id: Optional[int], name: str, roll_no: Optional[str] = None,
                 department: Optional[str] = None, contact: Optional[str] = None,
                 address: Optional[str] = None):
        self.id = id
        self.name = name
        self.roll_no = roll_no
        self.department = department
        self.contact = contact
        self.address = address

    def __repr__(self):
        return f"<Student id={self.id} name={self.name} roll_no={self.roll_no}>"

class HostelRoom:
    def __init__(self, id: Optional[int], block: Optional[str], room_no: Optional[str], capacity: int = 1):
        self.id = id
        self.block = block
        self.room_no = room_no
        self.capacity = capacity

    def __repr__(self):
        return f"<Room {self.block}-{self.room_no} cap={self.capacity} id={self.id}>"

class Bus:
    def __init__(self, id: Optional[int], registration: str, capacity: int = 20, driver_id: Optional[int] = None):
        self.id = id
        self.registration = registration
        self.capacity = capacity
        self.driver_id = driver_id

    def __repr__(self):
        return f"<Bus reg={self.registration} cap={self.capacity} id={self.id}>"

class Route:
    def __init__(self, id: Optional[int], name: str, pickup_location: str, bus_id: Optional[int] = None, fee: float = 0.0):
        self.id = id
        self.name = name
        self.pickup_location = pickup_location
        self.bus_id = bus_id
        self.fee = fee

    def __repr__(self):
        return f"<Route {self.name} pickup={self.pickup_location} fee={self.fee} id={self.id}>"
