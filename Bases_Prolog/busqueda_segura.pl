% Busqueda con predicado fijo.
% Los filtros llegan desde Python como atomos validados y citados; aqui solo
% se usan como datos (subcadenas a buscar), nunca como objetivos.
% Un filtro '' significa "sin filtro" para ese campo.

buscar_aves(FNombre, FColor, FHabitat, FPeso, FAlimento,
            Nombre, Reino, Filo, Color, Peso, Alimento, Habitat, Descripcion) :-
    caracteristicas(Nombre, Reino, Filo, Color, Peso, Alimento, Habitat, Descripcion),
    contiene(Nombre, FNombre),
    contiene(Color, FColor),
    contiene(Habitat, FHabitat),
    contiene(Peso, FPeso),
    contiene(Alimento, FAlimento).

contiene(_, '') :- !.
contiene(Texto, Filtro) :-
    atom(Filtro),
    once(sub_string(Texto, _, _, _, Filtro)).
