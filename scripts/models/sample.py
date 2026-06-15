class Sample:
    """
    Représente un sample pour un TRID donné.
    Contient uniquement les deux allèles.
    """
    def __init__(self, name):
        self.name = name
        self.allele1 = None
        self.allele2 = None

        self.result = None

    def __repr__(self):
        return f"<Sample {self.name} | A1={self.allele1} | A2={self.allele2}>"