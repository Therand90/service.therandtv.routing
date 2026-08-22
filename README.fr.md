[English](README.md) | [Français](README.fr.md)

# TherandTV Routing

[![Tests](https://github.com/Therand90/service.therandtv.routing/actions/workflows/tests.yml/badge.svg)](https://github.com/Therand90/service.therandtv.routing/actions/workflows/tests.yml)
[![Contrôles de politique du dépôt](https://github.com/Therand90/service.therandtv.routing/actions/workflows/repository-policy.yml/badge.svg)](https://github.com/Therand90/service.therandtv.routing/actions/workflows/repository-policy.yml)

Service Kodi compagnon de [`plugin.video.therandtv`](https://github.com/Therand90/plugin.video.therandtv). Il applique le routage requis par la lecture, supervise le démarrage des chaînes live et passe à la source suivante lorsqu’un démarrage échoue.

> [!IMPORTANT]
> Ce service est conçu pour les systèmes Linux/LibreELEC où les changements de route sont délégués à des scripts shell locaux. Il n’intègre aucune configuration VPN, aucun identifiant, aucune clé privée WireGuard ni aucun contenu de fournisseur.

## Responsabilités

- appliquer temporairement une route française/full-tunnel lorsqu’elle est demandée ;
- restaurer la route normale/split pour les contenus belges et l’accès Internet ordinaire ;
- acquitter l’activation de la route avant que le plugin ne résolve la lecture ;
- décoder, valider et ordonner les candidats de failover live ;
- superviser le démarrage Kodi et essayer le candidat suivant en cas d’échec ;
- placer brièvement les candidats défaillants en cooldown pour éviter leur réutilisation immédiate ;
- restaurer le routage split au démarrage et à l’arrêt du service.

Le service cesse volontairement de superviser une source dès que Kodi déclenche `onAVStarted`. La récupération d’un flux qui meurt après un démarrage réussi n’appartient pas encore à cette phase du failover.

## Relation avec TherandTV

Le plugin vidéo et ce service communiquent localement au moyen de propriétés de la fenêtre Home de Kodi. Le plugin écrit d’abord les données de requête, puis un identifiant unique en dernier. Le service considère cet identifiant comme le marqueur atomique de transmission et n’écrit l’identifiant « prêt » qu’une fois la route et la source préparées.

Pour une installation manuelle par ZIP, installez ce service avant `plugin.video.therandtv`. Un futur dépôt Kodi Therand pourra distribuer les deux extensions et résoudre automatiquement la dépendance.

## Modèle de routage

Le modèle validé sur LibreELEC utilise deux rôles indépendants :

- une interface WireGuard de sortie française utilisée uniquement lorsqu’une source exige une IP publique française ;
- un tunnel privé indépendant facultatif utilisé pour les services privés du VPS et jamais modifié par le basculement FR/normal.

En mode normal/split, l’interface LAN/Wi-Fi habituelle conserve la route Internet par défaut. Le tunnel français peut rester connecté, mais toute route par défaut injectée par ce tunnel est supprimée. En mode français/full, le service exécute le script dédié qui maintient l’endpoint WireGuard joignable via l’interface normale avant de déplacer la route par défaut vers le tunnel français.

Aucune valeur réseau personnelle n’est stockée dans ce dépôt public. Les scripts de référence lisent leurs valeurs locales dans :

```text
/storage/.config/therandtv-routing.conf
```

Partez de l’exemple fourni :

```sh
cp scripts/therandtv-routing.conf.example /storage/.config/therandtv-routing.conf
```

Puis adaptez la copie à la machine cible. Les adresses de l’exemple sont réservées à la documentation et ne doivent pas être utilisées telles quelles.

## Scripts d’exécution

Par défaut, le service Kodi exécute :

```text
/storage/.config/wg-fr-full-routing.sh
/storage/.config/wg-split-routing.sh
```

Des implémentations de référence sont fournies dans :

```text
scripts/wg-fr-full-routing.sh
scripts/wg-split-routing.sh
```

Une installation LibreELEC classique copie les scripts et la configuration dans `/storage/.config/`, rend les scripts exécutables puis ne modifie que le fichier de configuration local :

```sh
cp scripts/wg-fr-full-routing.sh /storage/.config/wg-fr-full-routing.sh
cp scripts/wg-split-routing.sh /storage/.config/wg-split-routing.sh
cp scripts/therandtv-routing.conf.example /storage/.config/therandtv-routing.conf
chmod +x /storage/.config/wg-fr-full-routing.sh /storage/.config/wg-split-routing.sh
```

Les copies du dépôt servent de références pour la reconstruction et la revue. Une mise à jour du dépôt GitHub ne remplace pas automatiquement les fichiers déjà copiés sur LibreELEC.

## Failover des sources live

Le service accepte un payload compressé et borné décrivant les sources candidates. `failover.py` valide notamment la taille du payload, la taille décompressée, le nombre de sources, les valeurs de routage et les schémas des cibles avant de renvoyer les candidats normalisés.

Les familles sont actuellement ordonnées ainsi :

1. Catch-up TV & More ;
2. le proxy VAVOO local sur le port loopback `8899` ;
3. les autres cibles HTTP(S) ou plugins Kodi.

La source sélectionnée reçoit un délai de démarrage adapté à sa famille. En cas d’échec, le service demande le candidat suivant. Une source logique VAVOO n’est pas placée en cooldown pendant cinq minutes simplement parce que son proxy local poursuit encore sa propre récupération au moment où le timeout externe expire.

## Coexistence avec `service.therand.autotrailer`

Kodi expose un seul lecteur vidéo ; une bande-annonce génère donc les mêmes callbacks `xbmc.Player` qu’une chaîne live. Le service de routage ignore ces callbacks lorsque le service de bandes-annonces Therand indique explicitement qu’il possède le lecteur via ses propriétés Home. Une bande-annonce simplement « pending » ne désactive pas l’observation normale de TherandTV.

Cette isolation ne modifie ni le skin ni le service de bandes-annonces ; elle empêche seulement des callbacks sans rapport d’acquitter ou de fermer une session de routage TherandTV.

## Notes de sécurité

Les scripts de routage modifient la route par défaut du système d’exploitation et doivent être considérés comme une configuration locale privilégiée. Relisez-les avant de les copier sur une machine et gardez `/storage/.config/therandtv-routing.conf` privé.

Ne versionnez jamais :

- des clés privées WireGuard ;
- de vrais identifiants VPN ;
- des jetons de services privés ;
- des adresses d’endpoint personnelles ou des détails de topologie interne, sauf publication volontaire.

Le dépôt fournit volontairement uniquement un exemple de configuration générique. Pour signaler une vulnérabilité, consultez [SECURITY.fr.md](SECURITY.fr.md).

## Développement et validation

GitHub Actions exécute les tests unitaires des helpers purs de failover, compile les fichiers Python, analyse le manifeste Kodi et vérifie la syntaxe des scripts shell de référence. Les Actions sont épinglées sur des SHA de commit complets.

## Projet lié

- [TherandTV](https://github.com/Therand90/plugin.video.therandtv) — passerelle vidéo Kodi et client de failover.

## Licence

Ce dépôt est distribué sous [licence MIT](LICENSE).
